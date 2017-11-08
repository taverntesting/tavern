import os


def check_env_var_settings(settings):
    """ Check the 'from_env_var' dictionary for environment variables

    Go through all of the keys in the 'from_env_var' part of the config file (if
    any), and check the environment variables present, replacing the default
    settings in the config file.
    """

    def check_recurse(to_update, to_check):
        # for each key to check
        for env_key in to_check:
            var_spec = to_check[env_key]

            # see if it's a list or a dictioanry - if it's a dictionary,
            # recurse until it hits a list, otherwise loop through the list
            # of environment variables and see if any of them are set
            if isinstance(var_spec, dict):
                check_recurse(to_update[env_key], var_spec)
            else:
                for env_var in var_spec:
                    if isinstance(env_var, list):
                        # There might be multiple ones to connect - check both are
                        # present, then chain them together in the order they're
                        # specified in in the input.
                        all_envs = [os.getenv(v) for v in env_var]

                        # If they were all present
                        if all(v != None for v in all_envs):
                            to_update[env_key] = "".join(all_envs)
                            break

                    else:
                        # If only one was defined, only check for it.
                        checked_env = os.getenv(env_var)

                        if checked_env:
                            to_update[env_key] = checked_env
                            break

    # for each key to override:
    #print(settings)
    check_recurse(settings, settings.get("$from_env_var", {}))
