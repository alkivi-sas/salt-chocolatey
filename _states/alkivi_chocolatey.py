"""
Manage Chocolatey package installs
.. versionadded:: 2016.3.0

.. note::
    Chocolatey pulls data from the Chocolatey internet database to determine
    current versions, find available versions, etc. This is normally a slow
    operation and may be optimized by specifying a local, smaller chocolatey
    repo.
"""

import salt.utils.data
import salt.utils.versions
from salt.exceptions import SaltInvocationError


def __virtual__():
    """
    Load only if chocolatey is loaded
    """
    if "chocolatey.install" in __salt__:
        return "alkivi_chocolatey"
    return (False, "chocolatey module could not be loaded")


def source_present(
    name,
    source_location,
    enabled=True,
    username=None,
    password=None,
    allow_self_service=False,
    admin_only=False,
):
    """
    Installs a source if not already installed

    Args:

        name (str):
            The name of the source to be installed. Required.

        source_location (str):
            The location of the source to be installed.

        allow_self_service (bool):
            Enable Self-Service (C4B feature)

        admin_only (bool):
            Source visible only for Admin (C4B feature)

    .. code-block:: yaml

        source-source:
          chocolatey.source_present:
            - name: sourcename
            - location: 'https://wwww'
            - admin_only: True
    """
    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    # Get list of currently installed sources
    sources = __salt__["alkivi_chocolatey.list_sources"]()
    need_changes = {}
    need_to_remove = False
    if name in sources:
        source = sources[name]
        if enabled == bool(source["Disabled"]):
            need_changes['enabled'] = enabled
        if allow_self_service != bool(source["Self-Service"]):
            need_changes['allow_self_service'] = allow_self_service
            need_to_remove = True
        if admin_only != bool(source["Admin-Only"]):
            need_changes['admin_only'] = admin_only 
            need_to_remove = True


    # Package not installed
    if need_to_remove:
        ret["changes"] = {name: "Will be re-created with correct params"}
    elif 'enabled' in need_changes:
        if need_changes['enabled']:
            ret["changes"] = {name: "Will be enabled."}
        else:
            ret["changes"] = {name: "Will be disabled."}

    if __opts__["test"]:
        ret["result"] = None
        return ret

    if need_to_remove:
        result = __salt__["alkivi_chocolatey.remove_source"](name)
        if "Running chocolatey failed" in result:
            raise CommandExecutionError('tototo')
        result = __salt__["alkivi_chocolatey.add_source"](name, source_location,
                                                          username=username,
                                                          password=password,
                                                          allow_self_service=allow_self_service,
                                                          admin_only=admin_only)
    elif 'enabled' in need_changes:
        if need_changes['enabled']:
            result = __salt__["chocolatey.enable_source"](name)
        else:
            result = __salt__["chocolatey.disable_source"](name)


    return ret

def source_absent(
    name,
):
    """
    Installs a source if not already installed

    Args:

        name (str):
            The name of the source to be installed. Required.

    .. code-block:: yaml

        source-source:
          chocolatey.source_absent:
            - name: sourcename

    """
    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    # Get list of currently installed sources
    sources = __salt__["alkivi_chocolatey.list_sources"]()

    if name not in sources:
        ret["changes"] = {name: "Already absent."}
        return ret

    if __opts__["test"]:
        ret["result"] = None
        ret["changes"] = {name: "Will be removed."}
        return ret

    result = __salt__["alkivi_chocolatey.remove_source"](name)

    return ret
