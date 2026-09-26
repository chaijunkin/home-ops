{
  description = "Strix Halo AI Worker Configuration";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    disko.url = "github:nix-community/disko";
    disko.inputs.nixpkgs.follows = "nixpkgs";
    gufo.url = "github:gufo-org/gufo";
  };

  outputs = { self, nixpkgs, disko, gufo }: {
    nixosConfigurations.strix-halo = nixpkgs.lib.nixosSystem {
      system = "x86_64-linux";
      specialArgs = { inherit gufo; };
      modules = [
        disko.nixosModules.disko
        ./configuration.nix
      ];
    };
  };
}
