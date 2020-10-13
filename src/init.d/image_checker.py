#!/usr/bin/python

# Copyright (c) Microsoft Corporation
# All rights reserved.
#
# MIT License
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the "Software"), to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
# to permit persons to whom the Software is furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
# BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
# DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import argparse
import base64
import copy
import http
import logging
import os
import re
import sys

import requests
import yaml

#pylint: disable=wrong-import-position
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from common.exceptions import ImageAuthenticationError, ImageCheckError, ImageNameError, UnknownError
import common.utils as utils

LOGGER = logging.getLogger(__name__)

# The workflow, refer to: https://docs.docker.com/registry/spec/auth/token/
# 1. send registry v2 request, if registry doesn't support v2 api, ignore image check
# 2. try to call v2 api to get image manifest. If return 401, do following steps
# 3. use WWW-Authenticate header returned from previous request to generate auth info
# 4. use generated auth info to get token
# 5. try to get image manifest with returned token. If succeed, the image is found in registry

BEARER_AUTH = "Bearer"
BASIC_AUTH = "Basic"
DEFAULT_REGISTRY = "https://index.docker.io/v2/"


def _get_registry_uri(uri) -> str:
    ret_uri = uri.strip().rstrip("/")
    if not ret_uri.startswith("http") and not ret_uri.startswith("https"):
        ret_uri = "https://{}".format(ret_uri)
    chunks = ret_uri.split('/')
    api_version_str = chunks[-1]
    if api_version_str in ("v1", "v2"):
        ret_uri = "/".join(chunks[:-1])
    ret_uri = ret_uri.rstrip("/") + "/v2/"
    return ret_uri


# Parse the challenge field, refer to: https://tools.ietf.org/html/rfc6750#section-3
def _parse_auth_challenge(challenge) -> dict:
    if not challenge.strip().startswith((BASIC_AUTH, BEARER_AUTH)):
        LOGGER.info("Challenge not supported, ignore this")
        return {}

    auth_type = BASIC_AUTH if challenge.strip().startswith(
        BASIC_AUTH) else BEARER_AUTH
    challenge_dict = {auth_type: {}}
    chunks = challenge.strip()[len(auth_type):].split(",")
    for chunk in chunks:
        pair = chunk.strip().split("=")
        challenge_dict[auth_type][pair[0]] = pair[1].strip("\"")
    return challenge_dict


class ImageChecker():  #pylint: disable=too-few-public-methods
    """
    Class used to precheck docker image.

    Notice: the image checker only works for docker registry which support v2 API and
    enables https. For registry using v1 API or doesn't enable https. This check will passed,
    and wrong image name may cause task hang.

    Image checker will try to check image with best effort. If registry return unexpected
    code such as 5xx/429, image checker will abort. We only failed the image checker when we make
    sure the image is not exist or authentication failed.
    """
    def __init__(self, job_config, secret):
        prerequisites = job_config["prerequisites"]
        task_role_name = os.getenv("PAI_CURRENT_TASK_ROLE_NAME")
        task_role = job_config["taskRoles"][task_role_name]
        docker_image_name = task_role["dockerImage"]

        docker_images = list(
            filter(lambda pre: pre["name"] == docker_image_name,
                   prerequisites))
        assert len(docker_images) == 1
        image_info = docker_images[0]

        self._image_uri = image_info["uri"]
        self._registry_uri = self._get_registry_from_image_uri(
            image_info["uri"])
        self._basic_auth_headers = {}
        self._bearer_auth_headers = {}
        self._registry_auth_type = BASIC_AUTH

        if "auth" in image_info and secret:
            auth = image_info["auth"]
            self._init_auth_info(auth, secret)

    def _get_registry_from_image_uri(self, image_uri) -> str:
        if self._is_default_domain_used():
            return DEFAULT_REGISTRY
        index = self._image_uri.find("/")
        return _get_registry_uri(image_uri[:index])

    def _init_auth_info(self, auth, secret) -> None:
        if "registryuri" in auth:
            registry_uri = _get_registry_uri(auth["registryuri"])
            if self._is_default_domain_used(
            ) and registry_uri != DEFAULT_REGISTRY:
                LOGGER.info(
                    "Using default registry for image %s, ignore auth info",
                    self._image_uri)
                return

        username = auth["username"] if "username" in auth else ""
        password = utils.render_string_with_secrets(
            auth["password"], secret) if "password" in auth else ""

        # Only set auth info if username/password present
        if username and password:
            basic_auth_token = base64.b64encode(
                bytes("{}:{}".format(username, password), "utf8")).decode()
            self._basic_auth_headers["Authorization"] = "{} {}".format(
                BASIC_AUTH, basic_auth_token)
            self._registry_uri = registry_uri

    # Refer: https://github.com/docker/distribution/blob/a8371794149d1d95f1e846744b05c87f2f825e5a/reference/normalize.go#L91
    def _is_default_domain_used(self) -> bool:
        index = self._image_uri.find("/")
        return index == -1 or all(ch not in [".", ":"]
                                  for ch in self._image_uri[:index])

    def _get_and_set_token(self, challenge) -> None:
        if not challenge or BEARER_AUTH not in challenge:
            LOGGER.info("Not using bearer token, use basic auth")
            return
        if "realm" not in challenge[BEARER_AUTH]:
            LOGGER.warning("realm not in challenge, use basic auth")
            return
        url = challenge[BEARER_AUTH]["realm"]
        parameters = copy.deepcopy(challenge[BEARER_AUTH])
        del parameters["realm"]
        resp = requests.get(url,
                            headers=self._basic_auth_headers,
                            params=parameters)
        if resp.status_code == http.HTTPStatus.UNAUTHORIZED:
            raise ImageAuthenticationError("Failed to get auth token")
        if not resp.ok:
            raise UnknownError("Unknown failure with resp code {}".format(
                resp.status_code))
        body = resp.json()
        self._bearer_auth_headers["Authorization"] = "{} {}".format(
            BEARER_AUTH, body["access_token"])
        self._registry_auth_type = BEARER_AUTH

    def _is_registry_v2_supportted(self) -> bool:
        try:
            resp = requests.head(self._registry_uri, timeout=10)
            if resp.ok or resp.status_code == http.HTTPStatus.UNAUTHORIZED:
                return True
            return False
        except (TimeoutError, ConnectionError):
            return False

    def _login_v2_registry(self, attempt_url) -> None:
        if not self._is_registry_v2_supportted():
            LOGGER.warning(
                "Registry %s may not support v2 api, ignore image check",
                self._registry_uri)
            raise UnknownError("Failed to check registry v2 support")
        resp = requests.head(attempt_url)
        if resp.ok:
            return
        headers = resp.headers
        if resp.status_code == http.HTTPStatus.UNAUTHORIZED and "Www-Authenticate" in headers:
            challenge = _parse_auth_challenge(headers["Www-Authenticate"])
            self._get_and_set_token(challenge)
            return
        if resp.status_code == http.HTTPStatus.UNAUTHORIZED:
            raise ImageAuthenticationError("Failed to login registry")
        LOGGER.error(
            "Failed to login registry or get auth url, resp code is %d",
            resp.status_code)
        raise UnknownError("Unknown status when trying to login registry")

    def _get_normalized_image_info(self) -> dict:
        uri = self._image_uri
        use_default_domain = self._is_default_domain_used()
        if not use_default_domain:
            assert "/" in self._image_uri
            index = self._image_uri.find("/")
            uri = self._image_uri[index + 1:]

        uri_chunks = uri.split(":")
        tag = "latest" if len(uri_chunks) == 1 else uri_chunks[1]
        repository = uri_chunks[0]
        if not re.fullmatch(r"[a-z\-_.0-9]+[\/a-z\-_.0-9]*",
                            repository) or not re.fullmatch(
                                r"[a-z\-_.0-9]+", tag):
            raise ImageNameError("image uri {} is invalid".format(
                self._image_uri))

        repo_chunks = uri_chunks[0].split("/")
        if len(repo_chunks) == 1 and use_default_domain:
            return {"repo": "library/{}".format(repository), "tag": tag}
        return {"repo": repository, "tag": tag}

    @utils.enable_request_debug_log
    def is_docker_image_accessible(self):
        try:
            image_info = self._get_normalized_image_info()
        except ImageNameError:
            LOGGER.error("docker image uri: %s is invalid",
                         self._image_uri,
                         exc_info=True)
            return False

        url = "{}{repo}/manifests/{tag}".format(self._registry_uri,
                                                **image_info)
        try:
            self._login_v2_registry(url)
        except ImageCheckError:
            LOGGER.error("Login failed, username or password is incorrect",
                         exc_info=True)
            return False

        if self._registry_auth_type == BEARER_AUTH:
            resp = requests.head(url, headers=self._bearer_auth_headers)
        else:
            resp = requests.head(url, headers=self._basic_auth_headers)
        if resp.ok:
            LOGGER.info("image %s found in registry", self._image_uri)
            return True
        if resp.status_code == http.HTTPStatus.NOT_FOUND or resp.status_code == http.HTTPStatus.UNAUTHORIZED:
            LOGGER.error(
                "image %s not found or user unauthorized, registry is %s, resp code is %d",
                self._image_uri, self._registry_uri, resp.status_code)
            return False
        LOGGER.warning("resp with code %d, ignore image check",
                       resp.status_code)
        raise UnknownError("Unknown response from registry")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("job_config", help="job config yaml")
    parser.add_argument("secret_file", help="secret file path")
    args = parser.parse_args()

    LOGGER.info("get job config from %s", args.job_config)
    with open(args.job_config) as config:
        job_config = yaml.safe_load(config)

    if not os.path.isfile(args.secret_file):
        job_secret = None
    else:
        with open(args.secret_file) as f:
            job_secret = yaml.safe_load(f.read())

    LOGGER.info("Start checking docker image")
    image_checker = ImageChecker(job_config, job_secret)
    try:
        if not image_checker.is_docker_image_accessible():
            sys.exit(1)
    except Exception:  #pylint: disable=broad-except
        LOGGER.warning("Failed to check image", exc_info=True)


if __name__ == "__main__":
    utils.init_logger()
    main()
