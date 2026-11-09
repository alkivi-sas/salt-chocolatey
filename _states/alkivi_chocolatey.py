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
from salt.exceptions import SaltInvocationError, CommandExecutionError
import logging


def __virtual__():
    """
    Load only if chocolatey is loaded
    """
    if "chocolatey.install" in __salt__:
        return "alkivi_chocolatey"
    return (False, "chocolatey module could not be loaded")


def installed(
    name,
    version=None,
    source=None,
    force=False,
    pre_versions=False,
    install_args=None,
    override_args=False,
    force_x86=False,
    package_args=None,
    allow_multiple=False,
    execution_timeout=None,
):
    """
    Faster drop-in for ``chocolatey.installed``.

    Reads the local package list once per run (cached) and never queries the
    remote feed, so an up-to-date package costs no choco call. Packages whose
    name contains "chocolatey" are seen as installed (upstream skips them and
    reinstalls them on every run).

    .. code-block:: yaml

        install_firefox:
          alkivi_chocolatey.installed:
            - name: firefox
    """
    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    installed_versions = __salt__["alkivi_chocolatey.list_local"]().get(name)
    current = installed_versions[0] if installed_versions else None

    if current is None:
        ret["comment"] = "{0} {1} will be installed".format(name, version or "latest")
    elif version and not salt.utils.versions.compare(ver1=current, oper="==", ver2=version):
        if allow_multiple:
            ret["comment"] = "{0} {1} will be installed side by side with {2}".format(name, version, current)
        else:
            ret["comment"] = "{0} {1} will be installed over {2}".format(name, version, current)
            force = True
    elif force:
        ret["comment"] = "{0} {1} will be reinstalled".format(name, current)
    else:
        ret["comment"] = "{0} {1} is already installed".format(name, current)
        return ret

    if __opts__["test"]:
        ret["result"] = None
        ret["changes"] = {name: {"old": current or "", "new": version or "latest"}}
        return ret

    try:
        __salt__["alkivi_chocolatey.install"](
            name=name,
            version=version,
            source=source,
            force=force,
            pre_versions=pre_versions,
            install_args=install_args,
            override_args=override_args,
            force_x86=force_x86,
            package_args=package_args,
            allow_multiple=allow_multiple,
            execution_timeout=execution_timeout,
        )
    except CommandExecutionError as exc:
        ret["result"] = False
        ret["comment"] = "Failed to install {0}: {1}".format(name, exc)
        return ret

    new_versions = __salt__["alkivi_chocolatey.list_local"]().get(name)
    ret["comment"] = "{0} installed successfully".format(name)
    ret["changes"] = {name: {"old": current or "", "new": new_versions[0] if new_versions else ""}}
    return ret


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
    need_to_create = False

    if name in sources:
        source = sources[name]
        if enabled == (source["Disabled"] == 'True'):
            need_changes['enabled'] = enabled
        if allow_self_service != (source["Self-Service"] == 'True'):
            need_changes['allow_self_service'] = allow_self_service
            need_to_remove = True
        if admin_only != (source["Admin-Only"] == 'True'):
            need_changes['admin_only'] = admin_only 
            need_to_remove = True
        if source_location != source["URL: "]:
            need_changes['source_location'] = source_location
            need_to_remove = True
        if username is not None and password is not None:
            need_to_remove = True
    else:
        need_to_create = True

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
        ret["changes"] = {name: "Was recreated."}
        ret["comment"] = result

    elif 'enabled' in need_changes:
        if need_changes['enabled']:
            result = __salt__["chocolatey.enable_source"](name)
            ret["changes"] = {name: "Was enabled."}
            ret["comment"] = result
        else:
            result = __salt__["chocolatey.disable_source"](name)
            ret["changes"] = {name: "Was disabled."}
            ret["comment"] = result
    elif need_to_create:
        result = __salt__["alkivi_chocolatey.add_source"](name, source_location,
                                                          username=username,
                                                          password=password,
                                                          allow_self_service=allow_self_service,
                                                          admin_only=admin_only)
        ret["changes"] = {name: "Was created."}
        ret["comment"] = result

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
        return ret

    if __opts__["test"]:
        ret["result"] = None
        ret["changes"] = {name: "Will be removed."}
        return ret

    result = __salt__["alkivi_chocolatey.remove_source"](name)
    ret["changes"] = {name: "Removed."}
    ret["comment"] = result

    return ret


def config(
    name,
    value,
):
    """
    Set a configuration value

    Args:

        name (str):
            The name of the config to set. Required.

        value(str):
            The value to set. Required.

    .. code-block:: yaml

        feature-chocolatey:
          chocolatey.config:
            - name: featurename
            - value: toto

    """
    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    current_value = __salt__["alkivi_chocolatey.get_config"](name)
    if current_value == value:
        ret["comment"] = "No change needed"
        return ret


    if __opts__["test"]:
        ret["result"] = None
        ret["changes"] = {name: "Will be setted to {0}.".format(value)}
        return ret

    result = __salt__["alkivi_chocolatey.set_config"](name, value)
    ret["changes"] = {name: "Set to {0}.".format(value)}
    ret["comment"] = result

    return ret


def feature_disabled(
    name,
):
    """
    Disable a feature if enable

    Args:

        name (str):
            The name of the feature to be installed. Required.

    .. code-block:: yaml

        feature-chocolatey:
          chocolatey.feature_disabled:
            - name: featurename

    """
    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    # Get list of currently installed features
    features = __salt__["alkivi_chocolatey.list_features"]()
    # If feature not in list -> Warning error
    if name not in features:
        raise CommandExecutionError('Feature {0} not present'.format(name))

    if name in features:
      feature = features[name]
      if not feature["Enabled"]:
          return ret
      else:
    # If feature in list, check status
    # If already disabled (status == False) -> OK+
    # Else disable_feature using module, additional if test
            if __opts__["test"]:
                ret["result"] = None
                ret["changes"] = {name: "Will be removed."}
                return ret

    result = __salt__["alkivi_chocolatey.disable_feature"](name)
    ret["changes"] = {name: "Disabled."}
    ret["comment"] = result

    return ret


def feature_enabled(
    name,
):
    """
    Enabled a feature if disable

    Args:

        name (str):
            The name of the feature to be installed. Required.

    .. code-block:: yaml

        feature-chocolatey:
          chocolatey.feature_enabled:
            - name: featurename

    """
    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    # Get list of currently installed features
    features = __salt__["alkivi_chocolatey.list_features"]()
    # If feature not in list -> Warning error
    if name not in features:
        raise CommandExecutionError('Feature {0} not present'.format(name))

    if name in features:
      feature = features[name]
      if feature["Enabled"]:
          return ret
      else:
    # If feature in list, check status
    # If already enabled (status == True) -> OK+
    # Else enable_feature using module, additional if test
            if __opts__["test"]:
                ret["result"] = None
                ret["changes"] = {name: "Will be removed."}
                return ret

    result = __salt__["alkivi_chocolatey.enable_feature"](name)
    ret["changes"] = {name: "Enabled."}
    ret["comment"] = result

    return ret

def feature_gui_disabled(
    name,
):
    """
    Disable a feature if enable

    Args:

        name (str):
            The name of the feature to be installed. Required.

    .. code-block:: yaml

        feature-chocolatey:
          chocolatey.feature_gui_disabled:
            - name: featurename

    """
    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    # Get list of currently installed features
    features = __salt__["alkivi_chocolatey.list_features_gui"]()
    # If feature not in list -> Warning error
    if name not in features:
        raise CommandExecutionError('Feature {0} not present'.format(name))

    if name in features:
      feature = features[name]
      if not feature["Enabled"]:
          return ret
      else:
    # If feature in list, check status
    # If already disabled (status == False) -> OK+
    # Else disable_feature using module, additional if test
            if __opts__["test"]:
                ret["result"] = None
                ret["changes"] = {name: "Will be removed."}
                return ret

    result = __salt__["alkivi_chocolatey.disable_feature_gui"](name)
    ret["changes"] = {name: "Disabled."}
    ret["comment"] = result

    return ret

def feature_gui_enabled(
    name,
):
    """
    Enabled a feature if disable

    Args:

        name (str):
            The name of the feature to be installed. Required.

    .. code-block:: yaml

        feature-chocolatey:
          chocolatey.feature_enabled:
            - name: featurename

    """
    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    # Get list of currently installed features
    features = __salt__["alkivi_chocolatey.list_features_gui"]()
    # If feature not in list -> Warning error
    if name not in features:
        raise CommandExecutionError('Feature {0} not present'.format(name))

    if name in features:
      feature = features[name]
      if feature["Enabled"]:
          return ret
      else:
    # If feature in list, check status
    # If already enabled (status == True) -> OK+
    # Else enable_feature using module, additional if test
            if __opts__["test"]:
                ret["result"] = None
                ret["changes"] = {name: "Will be removed."}
                return ret

    result = __salt__["alkivi_chocolatey.enable_feature_gui"](name)
    ret["changes"] = {name: "Enabled."}
    ret["comment"] = result

    return ret
