{
  description = "Strix Halo AI Worker Configuration";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    disko.url = "github:nix-community/disko";
    disko.inputs.nixpkgs.follows = "nixpkgs";
    gufo.url = "github:gufo-org/gufo/v0.5.0";
    sops-nix.url = "github:Mic92/sops-nix";
    sops-nix.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = { self, nixpkgs, disko, gufo, sops-nix }: {
    nixosConfigurations.strix-halo = nixpkgs.lib.nixosSystem {
      system = "x86_64-linux";
      specialArgs = { inherit gufo; };
      modules = [
        disko.nixosModules.disko
        sops-nix.nixosModules.sops
        ./configuration.nix
      ];
    };
  };
}
