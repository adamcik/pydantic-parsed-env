{
  description = "pydantic-parsed-env dev environment";

  nixConfig = {
    extra-substituters = [ "https://pydantic-parsed-env.cachix.org" ];
    extra-trusted-public-keys = [
      "pydantic-parsed-env.cachix.org-1:FHs6liQzz/PH8AFC5MMsqPaEaKxt5cjcBgqIyExq0AY="
    ];
  };

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-parts.url = "github:hercules-ci/flake-parts";
    nix-tooling.url = "github:adamcik/nix-tooling";
    nix-tooling.inputs.nixpkgs.follows = "nixpkgs";

    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs = {
        pyproject-nix.follows = "pyproject-nix";
        uv2nix.follows = "uv2nix";
        nixpkgs.follows = "nixpkgs";
      };
    };

    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

  };

  outputs =
    inputs@{
      flake-parts,
      pyproject-build-systems,
      pyproject-nix,
      uv2nix,
      ...
    }:
    flake-parts.lib.mkFlake { inherit inputs; } {
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];

      imports = [
        inputs.nix-tooling.flakeModules.formatting.common
        inputs.nix-tooling.flakeModules.formatting.python
      ];

      perSystem =
        { pkgs, ... }:
        let
          inherit (pkgs) lib;
          workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };
          python = pkgs.python312;
          mkPythonSet =
            group:
            (pkgs.callPackage pyproject-nix.build.packages { inherit python; }).overrideScope (
              lib.composeManyExtensions [
                pyproject-build-systems.overlays.default
                (workspace.mkPyprojectOverlay {
                  sourcePreference = "wheel";
                  dependencies = {
                    pydantic-parsed-env = [ group ];
                  };
                })
              ]
            );
          pythonSet = mkPythonSet "dev";

          env = pythonSet.mkVirtualEnv "pydantic-parsed-env" workspace.deps.default;
          devEnv = pythonSet.mkVirtualEnv "pydantic-parsed-env-dev" {
            pydantic-parsed-env = [ "dev" ];
          };
          mkCheck =
            venv: name: extraNativeBuildInputs: script:
            pkgs.runCommand name
              {
                src = ./.;
                nativeBuildInputs = [
                  venv
                  pkgs.uv
                ]
                ++ extraNativeBuildInputs;
              }
              ''
                cd "$src"
                export HOME="$TMPDIR"
                export UV_NO_SYNC=1
                export UV_PYTHON="${venv}/bin/python"
                export UV_PYTHON_DOWNLOADS=never
                export UV_NO_MANAGED_PYTHON=1
                ${script}
              '';
          pytestScript = ''
            export COVERAGE_FILE="$TMPDIR/.coverage"
            export HYPOTHESIS_STORAGE_DIRECTORY="$TMPDIR/.hypothesis"
            mkdir -p "$out"
            pytest \
              -q \
              --basetemp="$TMPDIR/.pytest_basetemp" \
              -o cache_dir="$TMPDIR/.pytest_cache" \
              --cov pydantic_parsed_env \
              --cov-report term-missing:skip-covered \
              --cov-report html:"$TMPDIR/htmlcov" \
              --cov-report xml:"$TMPDIR/coverage.xml"
            mv "$TMPDIR/htmlcov" "$out/htmlcov"
            mv "$TMPDIR/coverage.xml" "$out/coverage.xml"
          '';
          dependencyGroups = (builtins.fromTOML (builtins.readFile ./pyproject.toml)).dependency-groups;
          pinnedVersion =
            group: package:
            let
              prefix = "${package}==";
              dependency = lib.findFirst (
                dep: builtins.isString dep && lib.hasPrefix prefix dep
              ) (throw "Missing ${package} pin in ${group}") dependencyGroups.${group};
            in
            lib.removePrefix prefix dependency;
          compatibilityChecks = lib.genAttrs [ "compat-minimum" "compat-latest" ] (
            group:
            let
              packageSet = mkPythonSet group;
              venv = packageSet.mkVirtualEnv "pydantic-parsed-env-${group}" {
                pydantic-parsed-env = [ group ];
              };
            in
            mkCheck venv "pytest-${group}" [ ] ''
              python - <<'PY'
              from importlib.metadata import version
              import pydantic_parsed_env

              assert version("pydantic") == "${pinnedVersion group "pydantic"}"
              assert version("pydantic-settings") == "${pinnedVersion group "pydantic-settings"}"
              assert "site-packages" in pydantic_parsed_env.__file__
              PY
              ${pytestScript}
            ''
          );

        in
        {
          treefmt.programs.zizmor.enable = true;
          treefmt.settings.formatter.tombi-lint = {
            command = "${pkgs.tombi}/bin/tombi";
            includes = [ "*.toml" ];
            options = [
              "lint"
              "--offline"
            ];
          };

          packages.default = env;

          checks = {
            lock = mkCheck devEnv "uv-lock-check" [ python ] ''
              uv lock --check
              touch "$out"
            '';

            typing = mkCheck devEnv "pyright-check" [ pkgs.nodejs ] ''
              pyright src
              touch "$out"
            '';

            tests = compatibilityChecks.compat-latest;
          }
          // compatibilityChecks;

          devShells.default = pkgs.mkShell {
            shellHook = ''
              unset PYTHONPATH
              export REPO_ROOT=$(git rev-parse --show-toplevel)
              export UV_NO_SYNC=1
              export UV_PYTHON=${python.interpreter}
              export UV_PYTHON_DOWNLOADS=never
              export UV_NO_MANAGED_PYTHON=1
            '';

            packages = [
              pkgs.actionlint
              devEnv
              pkgs.nodejs
              pkgs.uv
              pkgs.tombi
              pkgs.zizmor
            ];
          };
        };
    };
}
