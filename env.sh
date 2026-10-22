# Source me (bash or zsh): `source env.sh`
# Sets up the ORFS/ASAP7 MCMM environment for this project.

if [ -n "${BASH_SOURCE[0]:-}" ]; then
  _env_src="${BASH_SOURCE[0]}"
else
  _env_src="${(%):-%x}"
fi
export PROJECT_ROOT="$(cd "$(dirname "$_env_src")" && pwd)"
unset _env_src

# Prebuilt arm64 OpenROAD/yosys from the RTL_STA project (ORFS @ 7421007).
# Point this elsewhere (e.g. a copy inside the project) to decouple.
export ORFS_TOOLS="${ORFS_TOOLS:-$HOME/Downloads/Projects/RTL_STA/designs/orfs_designs/tools/install}"

# Explicit executables take priority over PATH lookup in ORFS variables.mk,
# so the Homebrew yosys (no slang plugin) is never picked up.
export OPENROAD_EXE="$ORFS_TOOLS/OpenROAD/bin/openroad"
export OPENSTA_EXE="$ORFS_TOOLS/OpenROAD/bin/sta"
export YOSYS_EXE="$ORFS_TOOLS/yosys/bin/yosys"

export FLOW_HOME="$PROJECT_ROOT/third_party/OpenROAD-flow-scripts/flow"
export WORK_HOME="$PROJECT_ROOT/work"

# GNU make/sed/coreutils and bash 5 ahead of the macOS BSD versions;
# ORFS relies on GNU sed regexes (\s) and `realpath --relative-to`.
export PATH="/opt/homebrew/opt/make/libexec/gnubin:/opt/homebrew/opt/gnu-sed/libexec/gnubin:/opt/homebrew/opt/coreutils/libexec/gnubin:/opt/homebrew/bin:$ORFS_TOOLS/OpenROAD/bin:$ORFS_TOOLS/yosys/bin:$PATH"

if [ -f "$PROJECT_ROOT/.venv/bin/activate" ]; then
  . "$PROJECT_ROOT/.venv/bin/activate"
fi
