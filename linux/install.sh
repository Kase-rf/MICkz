#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
DATA_HOME=${XDG_DATA_HOME:-"$HOME/.local/share"}
APP_DIR="$DATA_HOME/mickz"
APPLICATIONS_DIR=${XDG_DATA_HOME:-"$HOME/.local/share"}/applications

if ! command -v python3 >/dev/null 2>&1; then
    echo "Erro: python3 não foi encontrado." >&2
    exit 1
fi
if ! python3 -c 'import tkinter' >/dev/null 2>&1; then
    echo "Erro: Tkinter não está disponível. No CachyOS, instale o pacote tk e execute este instalador novamente." >&2
    exit 1
fi
missing=""
for dependency in pactl ip; do
    if ! command -v "$dependency" >/dev/null 2>&1; then
        missing="$missing $dependency"
    fi
done
if [ -n "$missing" ]; then
    echo "Erro: faltam comandos necessários:$missing" >&2
    echo "No CachyOS/Arch, instale pipewire-pulse e iproute2; em outras distribuições, instale os pacotes equivalentes." >&2
    exit 1
fi

mkdir -p "$APP_DIR" "$APPLICATIONS_DIR"
install -m 0644 "$SCRIPT_DIR/mickz_gui.py" "$APP_DIR/mickz_gui.py"
install -m 0644 "$SCRIPT_DIR/mickz_receiver.py" "$APP_DIR/mickz_receiver.py"

cat > "$APP_DIR/launch.sh" <<'LAUNCHER'
#!/bin/sh
exec python3 "${XDG_DATA_HOME:-$HOME/.local/share}/mickz/mickz_gui.py" "$@"
LAUNCHER
chmod 0755 "$APP_DIR/launch.sh"

cat > "$APPLICATIONS_DIR/mickz.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=MICkz
Comment=Use o microfone do Android no Linux
Exec="$APP_DIR/launch.sh"
Icon=audio-input-microphone
Terminal=false
Categories=AudioVideo;Audio;
StartupNotify=true
DESKTOP
chmod 0644 "$APPLICATIONS_DIR/mickz.desktop"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true
fi

echo "MICkz instalado. Abra o menu de aplicativos e procure por MICkz."
echo "Receptor e interface copiados para: $APP_DIR"
