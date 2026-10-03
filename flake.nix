{
  description = "pydantic-parsed-env dev environment";

  nixConfig = {
    extra-substituters = ["https://pydantic-parsed-env.cachix.org"];
    extra-trusted-public-keys = ["pydantic-parsed-env.cachix.org-1:FHs6liQzz/PH8AFC5MMsqPaEaKxt5cjcBgqIyExq0AY="];
  };

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-parts.url = "github:hercules-ci/flake-parts";
    nix-tooling.url = "github:adamcik/nix-tooling/03474cbd37cedc82f533d69a65cdd23237b5798e";
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

  outputs = inputs @ {
    flake-parts,
    pyproject-build-systems,
    pyproject-nix,
    uv2nix,
    ...
  }:
    flake-parts.lib.mkFlake {inherit inputs;} {
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];

      imports = [
        inputs.nix-tooling.flakeModules.formatting.common
        inputs.nix-tooling.flakeModules.formatting.python
      ];

      perSystem = {pkgs, ...}: let
        workspace = uv2nix.lib.workspace.loadWorkspace {workspaceRoot = ./.;};
        overlay = workspace.mkPyprojectOverlay {
          sourcePreference = "wheel";
        };

        python = pkgs.python312;
        pythonSet =
          (pkgs.callPackage pyproject-nix.build.packages {inherit python;}).overrideScope
          (pkgs.lib.composeManyExtensions [
            pyproject-build-systems.overlays.default
            overlay
          ]);

        env = pythonSet.mkVirtualEnv "pydantic-parsed-env" workspace.deps.default;
        devEnv = pythonSet.mkVirtualEnv "pydantic-parsed-env-dev" workspace.deps.all;
        mkCheck = name: extraNativeBuildInputs: script:
          pkgs.runCommand name {
            src = ./.;
            nativeBuildInputs =
              [
                devEnv
                pkgs.uv
              ]
              ++ extraNativeBuildInputs;
          } ''
            cd "$src"
            export HOME="$TMPDIR"
            export UV_NO_SYNC=1
            export UV_PYTHON="${devEnv}/bin/python"
            export UV_PYTHON_DOWNLOADS=never
            export UV_NO_MANAGED_PYTHON=1
            ${script}
          '';

      in {
        packages.default = env;

        checks = {
          lock = mkCheck "uv-lock-check" [python] ''
            uv lock --check
            touch "$out"
          '';

          typing = mkCheck "pyright-check" [pkgs.nodejs] ''
            pyright src
            touch "$out"
          '';

          tests = mkCheck "pytest-check" [] ''
            export COVERAGE_FILE="$TMPDIR/.coverage"
            export HYPOTHESIS_STORAGE_DIRECTORY="$TMPDIR/.hypothesis"
            mkdir -p "$out"
            pytest \
              -q \
              --basetemp="$TMPDIR/.pytest_basetemp" \
              -o cache_dir="$TMPDIR/.pytest_cache" \
              --cov src/pydantic_parsed_env \
              --cov-report term-missing:skip-covered \
              --cov-report html:"$TMPDIR/htmlcov" \
              --cov-report xml:"$TMPDIR/coverage.xml"
            mv "$TMPDIR/htmlcov" "$out/htmlcov"
            mv "$TMPDIR/coverage.xml" "$out/coverage.xml"
          '';
        };

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
           ];
        };
      };
    };
}
