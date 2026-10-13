{
  description = "AI-HIL removable storage and pinned 3mdeb SDWire controller";
  inputs.nixpkgs.url = "https://releases.nixos.org/nixpkgs/nixpkgs-26.11pre1080219.8d5d270900d3/nixexprs.tar.zst";
  outputs = { self, nixpkgs }: let
    systems = [ "x86_64-linux" "aarch64-linux" ];
    each = f: nixpkgs.lib.genAttrs systems (system: f (import nixpkgs { inherit system; }));
    controller = pkgs: pkgs.stdenv.mkDerivation {
      pname = "sd-mux-ctrl";
      version = "2020-02-17-9dd189d";
      src = pkgs.fetchurl {
        name = "sd-mux-9dd189d.tar.gz";
        url = "https://codeload.github.com/3mdeb/sd-mux/tar.gz/9dd189d973da64e033a0c5c2adb3d94b23153d94";
        hash = "sha256-WJTaEqdQbPEMmSxTHRkyECFacAFgeDXufYIqxxYM5rk=";
      };
      nativeBuildInputs = [ pkgs.cmake pkgs.pkg-config ];
      buildInputs = [ pkgs.libftdi1 pkgs.popt ];
      cmakeFlags = [ "-DCMAKE_POLICY_VERSION_MINIMUM=3.5" ];
      # Upstream omits pkg-config include/link directories.
      env.NIX_CFLAGS_COMPILE = "-I${pkgs.libftdi1}/include/libftdi1";
    };
    source = builtins.path {
      path = ./labinstruments;
      name = "labinstruments-storage";
      filter = path: type: type == "directory" || nixpkgs.lib.hasSuffix ".py" path;
    };
    hil = pkgs: pkgs.writeShellApplication {
      name = "hil-storage";
      runtimeInputs = [ pkgs.python3 (controller pkgs) pkgs.bmaptool ];
      text = ''
        export PYTHONPATH=${pkgs.runCommand "hil-storage-python" {} "mkdir -p $out; cp -r ${source} $out/labinstruments"}
        exec python3 -m labinstruments.storage_cli "$@"
      '';
    };
  in {
    packages = each (pkgs: { default = hil pkgs; sd-mux-ctrl = controller pkgs; });
    devShells = each (pkgs: { default = pkgs.mkShell {
      packages = [ (hil pkgs) (controller pkgs) pkgs.python3 pkgs.util-linux pkgs.bmaptool ];
    }; });
  };
}
