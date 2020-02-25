SCRIPT_PATH="${BASH_SOURCE[0]}";
pushd `dirname ${SCRIPT_PATH}` > /dev/null
SCRIPT_PATH=`pwd -P`;
popd  > /dev/null

# For a csh environment, use this to get the script path
# and any export statement becomes a setenv
# set SCRIPT_PATH = `lsof +p $$ | \grep -oE /.\*setup.csh`
# set SCRIPT_PATH = `dirname $SCRIPT_PATH`

export PYTHONPATH="$SCRIPT_PATH"

