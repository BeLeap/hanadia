{
  description = "Hanadia Mono: Cascadia Code programming glyphs with Pretendard Hangul";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";

  outputs = { self, nixpkgs }:
    let
      systems = [
        "aarch64-darwin"
        "x86_64-darwin"
        "aarch64-linux"
        "x86_64-linux"
      ];
      forAllSystems = function: nixpkgs.lib.genAttrs systems function;

      cascadiaRevision = "v2407.24";
      cascadiaCommit = "56bcca3f2c1e4cb19458954f0e2bb4635960df91";
      cascadiaArchiveHash = "sha256-5npo7jOG22P0i5BUvRlup1K8ak67TfNa3OZzPaUMhHQ=";
      cascadiaLicenseHash = "sha256-UYgs0826ThbyIPRN2wimNcOMROpuCXXbJXT0vm+Vgjg=";

      pretendardRevision = "v1.3.9";
      pretendardCommit = "5c41199ea0024a9e0b2cb31735265056e5472d76";
      pretendardArchiveHash = "sha256-BL41GnTWv31gxICjCH5R0YVIXTWlICMUKvHfGeuMQoo=";
      pretendardLicenseHash = "sha256-0x3dnyvtMv1+MCogXPI4C6DeZSkVLSOe+Zz7byYb/AQ=";

      weights = [ "Light" "Regular" "SemiBold" "Bold" ];
      # Change only the value for Regular to "Medium" if a heavier Korean
      # regular cut is preferred.  The default deliberately matches weights.
      pretendardWeightFor = {
        Light = "Light";
        Regular = "Regular";
        SemiBold = "SemiBold";
        Bold = "Bold";
      };

      packages = forAllSystems (system:
        let
          pkgs = import nixpkgs { inherit system; };
          python = pkgs.python3.withPackages (pythonPackages: [
            pythonPackages.fonttools
          ]);
          cascadiaArchive = pkgs.fetchurl {
            url = "https://github.com/microsoft/cascadia-code/releases/download/${cascadiaRevision}/CascadiaCode-2407.24.zip";
            hash = cascadiaArchiveHash;
          };
          pretendardArchive = pkgs.fetchurl {
            url = "https://github.com/orioncactus/pretendard/releases/download/${pretendardRevision}/Pretendard-1.3.9.zip";
            hash = pretendardArchiveHash;
          };
          cascadiaLicense = pkgs.fetchurl {
            url = "https://raw.githubusercontent.com/microsoft/cascadia-code/${cascadiaCommit}/LICENSE";
            hash = cascadiaLicenseHash;
          };
          pretendardLicense = pkgs.fetchurl {
            url = "https://raw.githubusercontent.com/orioncactus/pretendard/${pretendardCommit}/LICENSE";
            hash = pretendardLicenseHash;
          };
          weightCommands = builtins.concatStringsSep "\n" (map
            (weight: ''
              python scripts/merge-font.py \
                --base "upstream/cascadia/ttf/static/CascadiaCode-${weight}.ttf" \
                --source "upstream/pretendard/public/static/alternative/Pretendard-${builtins.getAttr weight pretendardWeightFor}.ttf" \
                --output "merged/HanadiaMono-${weight}.ttf" \
                --weight "${weight}" \
                --cascadia-license LICENSES/Cascadia-Code-OFL.txt \
                --pretendard-license LICENSES/Pretendard-OFL.txt

              python scripts/verify-font.py \
                --font "merged/HanadiaMono-${weight}.ttf" \
                --style "${weight}"
            '')
            weights);
        in
        {
          default = pkgs.stdenvNoCC.mkDerivation {
            pname = "hanadia-mono";
            version = "0.1.0";
            src = ./.;

            nativeBuildInputs = [
              python
              pkgs.unzip
            ];

            dontConfigure = true;
            dontStrip = true;

            buildPhase = ''
              set -eu
              runHook preBuild

              # Fail closed if the checked-in notices no longer match the
              # exact licenses at the pinned upstream commits.
              cmp ${cascadiaLicense} LICENSES/Cascadia-Code-OFL.txt
              cmp ${pretendardLicense} LICENSES/Pretendard-OFL.txt

              mkdir -p upstream/cascadia upstream/pretendard merged
              unzip -q ${cascadiaArchive} 'ttf/static/CascadiaCode-*.ttf' -d upstream/cascadia
              unzip -q ${pretendardArchive} 'public/static/alternative/Pretendard-*.ttf' -d upstream/pretendard

              ${weightCommands}

              cat > BUILD-INFO.txt <<EOF
              Hanadia Mono source version: 0.1.0
              Cascadia Code revision: ${cascadiaRevision}
              Cascadia Code commit: ${cascadiaCommit}
              Cascadia Code archive hash: ${cascadiaArchiveHash}
              Pretendard revision: ${pretendardRevision}
              Pretendard commit: ${pretendardCommit}
              Pretendard archive hash: ${pretendardArchiveHash}
              EOF

              runHook postBuild
            '';

            installPhase = ''
              set -eu
              runHook preInstall

              install -d "$out/share/fonts/truetype"
              install -m 0644 merged/*.ttf "$out/share/fonts/truetype/"

              install -d "$out/share/licenses/hanadia-mono"
              install -m 0644 LICENSE "$out/share/licenses/hanadia-mono/LICENSE"
              install -m 0644 LICENSES/Cascadia-Code-OFL.txt "$out/share/licenses/hanadia-mono/"
              install -m 0644 LICENSES/Pretendard-OFL.txt "$out/share/licenses/hanadia-mono/"

              install -d "$out/share/doc/hanadia-mono"
              install -m 0644 BUILD-INFO.txt "$out/share/doc/hanadia-mono/"
              install -m 0644 README.md "$out/share/doc/hanadia-mono/"

              runHook postInstall
            '';
          };
        });
    in
    rec {
      inherit packages;

      checks = forAllSystems (system: {
        build = packages.${system}.default;
      });
    };
}
