# Microsoft OpenPAI Runtime

![Docker Pulls](https://img.shields.io/docker/pulls/openpairuntime/openpai-runtime) ![GitHub Workflow Status (branch)](https://img.shields.io/github/workflow/status/microsoft/openpai-runtime/CI/master)

**Runtime component for deep learning workload** 

In order to better support deep learning workload, [OpenPAI](https://github.com/microsoft/pai) implements "PAI Runtime", a module that provides runtime support to job containers. 
 
One major feature of PAI runtime is the instantiation of runtime environment variables. PAI runtime provides several built-in runtime environment variables, including the container role name and index, the IP, port of all the containers used in the job. With PAI runtime environment variables and [Framework Controller](https://github.com/microsoft/frameworkcontroller), user can onboard custom workload (e.g., MPI, TensorBoard) without the involvement of (or modification to) OpenPAI platform itself. OpenPAI further allows users to define custom runtime environment variables, tailored for their workload.
 
Another major feature of OpenPAI runtime is the introduction of "PAI runtime plugin".  The runtime plugin provides a way for users to customize their runtime behavior for a job container. Essentially, plugin is a generic method for user to inject some code during container initialization or container termination. OpenPAI implements several built-in plugins for desirable features, including a storage plugin that mounts to a remote storage service from within the job containers, an ssh plugin that supports ssh access to each container, and a failure analysis plugin that analyzes the failure reason when a container fails. We envision there will be more features implemented by the plugin mechanism.


## Features
1. Prepare OpenPAI runtime environment variables
3. Failure analysis: report possible job failure reason based on the failure pattern
4. Storage plugin: used to auto mount remote storage according to storage config
5. SSH plugin: used to support ssh access to job container
6. Cmd plugin: used to run customized commands before/after job

## How to build
Please run `docker build -f ./build/openpai-runtime.dockerfile .` to build openpai-runtime docker image

## Contributing

This project welcomes contributions and suggestions.  Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit https://cla.opensource.microsoft.com.

When you submit a pull request, a CLA bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., status check, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.
