{
  description = "pydantic-parsed-env dev environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-parts.url = "github:hercules-ci/flake-parts";

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

    treefmt-nix = {
      url = "github:numtide/treefmt-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = inputs @ {
    flake-parts,
    pyproject-build-systems,
    pyproject-nix,
    treefmt-nix,
    uv2nix,
    ...
  }:
    flake-parts.lib.mkFlake {inherit inputs;} {
      systems = [
        "x86_64-linux"
        "aarch64-linux"
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

        treefmtEval = treefmt-nix.lib.evalModule pkgs {
          projectRootFile = "flake.nix";
          programs = {
            alejandra.enable = true;
            actionlint.enable = true;
            prettier.enable = true;
            zizmor.enable = true;
          };
          settings.formatter = {
            ruff-check = {
              command = "${devEnv}/bin/ruff";
              includes = ["*.py"];
              options = ["check" "--fix"];
              priority = 10;
            };
            ruff-format = {
              command = "${devEnv}/bin/ruff";
              includes = ["*.py"];
              options = ["format"];
              priority = 20;
            };
            tombi-format = {
              command = "${pkgs.tombi}/bin/tombi";
              includes = ["*.toml"];
              options = ["format" "--offline"];
            };
            tombi-lint = {
              command = "${pkgs.tombi}/bin/tombi";
              includes = ["*.toml"];
              options = ["lint" "--offline"];
            };
          };
        };
      in {
        packages.default = env;
        formatter = treefmtEval.config.build.wrapper;

        checks = {
          treefmt = treefmtEval.config.build.check ./.;

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
            pkgs.tombi
            treefmtEval.config.build.wrapper
            pkgs.nodejs
            pkgs.uv
            pkgs.zizmor
          ];
        };
      };
    };
}
