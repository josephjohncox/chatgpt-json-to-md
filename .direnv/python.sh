# -*- mode: sh; -*-
# Custom global configuration for [direnv](https://direnv.net/)
# i.e. override/complete the direnv-stdlib:
#           https://github.com/direnv/direnv/blob/master/stdlib.sh
#
# Quick installation of this file:
#    mkdir -p ~/.config/direnv
#    cd ~/.config/direnv
#    curl -o direnvrc https://raw.githubusercontent.com/Falkor/dotfiles/master/direnv/direnvrc
#
# Sample .envrc you can use for Python projects based on the
# layouts defined in this file:
# https://github.com/Falkor/dotfiles/blob/master/direnv/envrc
#
############################ Python ############################
# Workfow based on:
# - 'pyenv' to easily switch to a special version of python
# - 'pyenv-virtualenv' to manage python versions AND virtualenvs
#
# Typical .envrc for your python project using the below functions:
#    if [ -f ".python-version" ]; then
#       pyversion=$(head .python-version)
#    else
#       pyversion=2.7.16
#    fi
#    pvenv=$(basename $PWD)
#
#    use python ${pyversion}
#    layout virtualenv ${pyversion} ${pvenv}
#    layout activate ${pvenv}
#
# Adapted from
#  - https://github.com/direnv/direnv/wiki/Python#-pyenv and
#  - https://github.com/direnv/direnv/wiki/Python#-virtualenvwrapper
#  - https://github.com/direnv/direnv/wiki/Python#venv-stdlib-module
#
# Side note:
# It appeared required to reload the pyenv [virtualenv-]init as for
# It May be due to the fact that direnv is creating a new bash
#  sub-process to load the stdlib, direnvrc and .envrc
###

# === Use a specific python version (with pyenv) ===
# Usage in .envrc:
#    use python <version>
use_python() {
    if has pyenv; then
        local pyversion=$1
        eval "$(pyenv init --path)"
        eval "$(pyenv init -)"
        pyenv local ${pyversion} || log_error "Could not find pyenv version '${pyversion}'. Consider running 'pyenv install ${pyversion}'"
    fi
}

# === Support for Python >=3.3 venv ===
# See https://github.com/direnv/direnv/wiki/Python#venv-stdlib-module
# Python 3.3 and later provide built-in support for virtual environments via the venv module in the standard library.
# Usage in .envrc:
#   export VIRTUAL_ENV_HOME=.venv    # Default: ~/venv
#   layout python-venv <name>        # creates ${VIRTUAL_ENV_HOME}/<name> venv
realpath() {
    [[ $1 = /* ]] && echo "$1" || echo "$PWD/${1#./}"
}
layout_python-venv() {
    local pvenv=$1

    VIRTUAL_ENV_HOME=${VIRTUAL_ENV_HOME:-~/venv}
    VIRTUAL_ENV=${VIRTUAL_ENV:-${VIRTUAL_ENV_HOME}/${pvenv}}
    unset PYTHONHOME
    export VIRTUAL_ENV
    if [[ ! -d $VIRTUAL_ENV ]]; then
        log_status "no venv found; creating $VIRTUAL_ENV"
        python3 -m venv "$VIRTUAL_ENV"
    fi
    PATH_add "${VIRTUAL_ENV}/bin"
}

# === Create a new virtualenv ===
# Usage in .envrc:
#    layout virtualenv <version> <name>
layout_virtualenv() {
    local pyversion=$1
    local pvenv=$2
    if has pyenv; then
        pyenv local ${pyversion}
        # if [ -n "$(which pyenv-virtualenv)" ]; then
            eval "$(pyenv virtualenv-init -)"
            pyenv virtualenv --quiet ${pyversion} ${pvenv}
        # else
         #   log_error "pyenv-virtualenv is not installed."
        #fi
    elif has python3; then
        # Use venv by default
        layout_python-venv ${pvenv}
    else
        log_error "pyenv or python3 venv not found."
    fi
}

# === Activate a virtualenv ===
# Note that pyenv-virtualenv uses 'python -m venv' if it is
# available (CPython 3.3 and newer) and  'virtualenv' otherwise
# Usage in .envrc:
#    layout activate <name>
layout_activate() {
    if has pyenv; then
        local pyenvprefix=$(pyenv prefix)
        local pyversion=$(pyenv version-name)
        local pvenv="$1"
        # Below initialization is necessary to recall ;(
        pyenv activate ${pvenv}
    else
        source ${VIRTUAL_ENV}/bin/activate
    fi
}


