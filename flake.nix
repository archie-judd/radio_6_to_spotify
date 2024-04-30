{
  inputs = {
    flake-utils.url = "github:numtide/flake-utils";
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-23.11";
    poetry2nix = {
      url = "github:nix-community/poetry2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, flake-utils, poetry2nix }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        _poetry2nix = poetry2nix.lib.mkPoetry2Nix { inherit pkgs; };
        my_env = _poetry2nix.mkPoetryEnv {
          projectDir = ./.;
          editablePackageSources = {
            radio_6_to_spotify = "${builtins.getEnv "PWD"}/src";
          };
          overrides = _poetry2nix.defaultPoetryOverrides.extend (self: super: {
            bs4 = super.bs4.overridePythonAttrs (old: {
              buildInputs = (old.buildInputs or [ ]) ++ [ super.setuptools ];
            });
          });
        };
      in {
        devShells.default = pkgs.mkShell {
          inputsFrom = [ my_env.env ];
          packages = [ pkgs.poetry ];
        };
      });
}
