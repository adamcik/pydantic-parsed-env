{
  description = "pydantic-simple-env dev environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-parts.url = "github:hercules-ci/flake-parts";

    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
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

      perSystem = {
        pkgs,
        self',
        ...
      }: let
        workspace = uv2nix.lib.workspace.loadWorkspace {workspaceRoot = ./.;};
        overlay = workspace.mkPyprojectOverlay {
          sourcePreference = "wheel";
        };

        treefmtEval = treefmt-nix.lib.evalModule pkgs {
          projectRootFile = "flake.nix";
          programs = {
            alejandra.enable = true;
            ruff-check.enable = true;
            ruff-format.enable = true;
          };
        };

        python = pkgs.python313;
        pythonSet =
          (pkgs.callPackage pyproject-nix.build.packages {inherit python;}).overrideScope
          (pkgs.lib.composeManyExtensions [
            pyproject-build-systems.overlays.default
            overlay
          ]);

        env = pythonSet.mkVirtualEnv "pydantic-simple-env" workspace.deps.default;
        devEnv = pythonSet.mkVirtualEnv "pydantic-simple-env-dev" workspace.deps.all;
      in {
        packages.default = env;
        formatter = treefmtEval.config.build.wrapper;

        checks = {
          treefmt = treefmtEval.config.build.check ./.;

          typing =
            pkgs.runCommand "pyright-check" {
              src = ./.;
              nativeBuildInputs = [
                devEnv
                pkgs.nodejs
              ];
            } ''
              cd "$src"
              export HOME="$TMPDIR"
              pyright src
              touch "$out"
            '';

          tests =
            pkgs.runCommand "pytest-check" {
              src = ./.;
              nativeBuildInputs = [devEnv];
            } ''
              cd "$src"
              export HOME="$TMPDIR"
              pytest -q
              touch "$out"
            '';
        };

        devShells.default = pkgs.mkShell {
          packages = [
            devEnv
            treefmtEval.config.build.wrapper
            pkgs.nodejs
            pkgs.uv
          ];
        };
      };
    };
}
