"""
SCons build file for NVDA Profile Manager

Targets:
    scons           - Build everything (icon + exe)
    scons icon      - Generate icon.ico
    scons build     - Build NVDAProfileManager.exe
    scons installer - Build + sign the exe, compile + sign the Inno Setup installer
    scons sign      - Sign the existing exe and installer (via sign-products.ps1)
    scons run       - Run the application
    scons clean     - Clean build artifacts

Signing uses the Certum SimplySign cloud certificate through the shared script in
the ownCloud secrets share (the single source of truth). No Certum material --
seed, certificate, or ssign.exe -- is stored in this repository; only the path to
that external script is referenced here.
"""

import os
import sys
import subprocess
import math
import time

# Environment setup
env = Environment(ENV=os.environ)

# Paths
ICON_FILE = 'icon.ico'
ICON_PREVIEW = 'icon_preview.png'
MAIN_SCRIPT = 'main.py'
EXE_NAME = 'NVDAProfileManager'
DIST_DIR = 'dist'

# Installer / signing
REPO_ROOT = Dir('.').abspath
ISS_FILE = os.path.join('installer', 'NVDAProfileManager.iss')
INSTALLER_OUTPUT_DIR = os.path.join('installer', 'output')

# Signing is delegated to the shared sign-products.ps1 in the ownCloud secrets
# share. That script owns the Certum SimplySign login and resolves the TOTP seed
# itself (CERTUM_OTP env, encrypted seed.enc via CERTUM_OTP_KEY, or
# otpauthuri.txt) -- none of which lives in this repository. Only the *location*
# is configured, via a local, git-ignored ssign.conf (see ssign.conf.example).
SIGN_CONF = 'ssign.conf'
DEFAULT_SIGN_DIR = (r'C:\Users\stefa\ownCloud\Personal\slohmaier.com'
                    r'\code-signing\certum-codesigning')


def load_sign_config():
    """Read the local ssign.conf (key = value), or an empty dict if absent."""
    cfg = {}
    path = os.path.join(REPO_ROOT, SIGN_CONF)
    if os.path.exists(path):
        with open(path, encoding='utf-8') as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, value = line.split('=', 1)
                cfg[key.strip()] = value.strip()
    return cfg


_sign_cfg = load_sign_config()
SIGN_DIR = (_sign_cfg.get('sign_dir')
            or os.environ.get('OWNCLOUD_SIGN_DIR')
            or DEFAULT_SIGN_DIR)
SIGN_SCRIPT = os.path.join(SIGN_DIR, _sign_cfg.get('sign_script', 'sign-products.ps1'))


def read_version():
    """Read VERSION from main.py (single source of truth for the app version)."""
    with open(os.path.join(REPO_ROOT, MAIN_SCRIPT), encoding='utf-8') as fh:
        for line in fh:
            if line.startswith('VERSION'):
                return line.split('=', 1)[1].strip().strip('"').strip("'")
    return '0.0.0'


def find_iscc():
    """Locate the Inno Setup compiler."""
    candidates = [
        r'C:\Program Files (x86)\Inno Setup 6\ISCC.exe',
        r'C:\Program Files\Inno Setup 6\ISCC.exe',
    ]
    for base in (os.environ.get('ProgramFiles(x86)', ''),
                 os.environ.get('ProgramFiles', '')):
        if base:
            candidates.append(os.path.join(base, 'Inno Setup 6', 'ISCC.exe'))
    for path in candidates:
        if path and os.path.exists(path):
            return path
    return None


def run_sign(include, retries=3, delay=45):
    """Sign files through the shared sign-products.ps1 (Certum SimplySign).

    ``include`` is a wildcard matched against full paths. The Certum backend
    accepts only one ssign login per short window, so a failed login (e.g. the
    setup sign right after the payload sign) is retried after a delay.
    """
    if not os.path.exists(SIGN_SCRIPT):
        print('Signing script not found: %s' % SIGN_SCRIPT)
        return False

    cmd = ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass',
           '-File', SIGN_SCRIPT, '-Include', include]
    for attempt in range(1, retries + 1):
        print('Signing (attempt %d/%d): %s' % (attempt, retries, include))
        result = subprocess.run(cmd)
        if result.returncode == 0:
            return True
        if attempt < retries:
            print('Signing failed; waiting %ds for the Certum login window...' % delay)
            time.sleep(delay)
    return False


def build_installer(target, source, env):
    """Sign the payload, compile the installer, then sign the Setup.exe."""
    iscc = find_iscc()
    if not iscc:
        print('ERROR: Inno Setup compiler (ISCC.exe) not found.')
        return 1

    version = read_version()

    # 1. Sign the payload first, so the exe embedded in Setup.exe is signed.
    if not run_sign(r'*nvdaprofilemanager\dist\*'):
        print('ERROR: payload signing failed.')
        return 1

    # 2. Compile the installer (embeds the now-signed payload).
    print('Compiling installer v%s...' % version)
    result = subprocess.run(
        [iscc, '/DMyAppVersion=%s' % version, ISS_FILE], cwd=REPO_ROOT)
    if result.returncode != 0:
        print('ERROR: ISCC failed (%d).' % result.returncode)
        return 1

    # 3. Sign the produced Setup.exe (fresh login).
    if not run_sign(r'*nvdaprofilemanager\installer\output\*'):
        print('ERROR: installer signing failed.')
        return 1

    print('Installer built and signed under %s' % INSTALLER_OUTPUT_DIR)
    return None


def sign_only(target, source, env):
    """Sign the existing exe and installer in place."""
    ok_payload = run_sign(r'*nvdaprofilemanager\dist\*')
    ok_setup = run_sign(r'*nvdaprofilemanager\installer\output\*')
    return None if (ok_payload and ok_setup) else 1


def generate_icon(target, source, env):
    """Generate the application icon using Pillow."""
    from PIL import Image, ImageDraw

    def draw_icon(size):
        """Draw the NVDA Profile Manager icon at the given size."""
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Scale factor
        s = size / 256

        # Colors - NVDA purple theme
        folder_color = (102, 51, 153)  # Purple
        folder_dark = (76, 38, 115)    # Darker purple for depth
        arrow_color = (255, 255, 255)  # White arrows for contrast

        # Draw folder body (back part)
        folder_back = [
            (30*s, 70*s),
            (226*s, 70*s),
            (226*s, 210*s),
            (30*s, 210*s)
        ]
        draw.polygon(folder_back, fill=folder_dark)

        # Draw folder tab
        tab = [
            (30*s, 70*s),
            (30*s, 50*s),
            (100*s, 50*s),
            (120*s, 70*s)
        ]
        draw.polygon(tab, fill=folder_dark)

        # Draw folder front
        folder_front = [
            (20*s, 85*s),
            (236*s, 85*s),
            (226*s, 220*s),
            (30*s, 220*s)
        ]
        draw.polygon(folder_front, fill=folder_color)

        # Draw circular arrows (sync symbol) in center
        cx, cy = 128*s, 155*s  # Center of arrows
        radius = 45*s
        arrow_width = max(2, int(12*s))

        # Draw two arc arrows
        for start_angle, end_angle in [(30, 150), (210, 330)]:
            # Draw arc
            bbox = (cx - radius, cy - radius, cx + radius, cy + radius)
            draw.arc(bbox, start_angle, end_angle, fill=arrow_color, width=arrow_width)

            # Draw arrowhead at end of arc
            end_rad = math.radians(end_angle)
            ax = cx + radius * math.cos(end_rad)
            ay = cy + radius * math.sin(end_rad)

            # Arrowhead points
            arrow_size = 18*s
            angle1 = end_rad + math.radians(150)
            angle2 = end_rad + math.radians(210)

            points = [
                (ax, ay),
                (ax + arrow_size * math.cos(angle1), ay + arrow_size * math.sin(angle1)),
                (ax + arrow_size * math.cos(angle2), ay + arrow_size * math.sin(angle2))
            ]
            draw.polygon(points, fill=arrow_color)

        return img

    # Generate icons at standard Windows ICO sizes
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = [draw_icon(size) for size in sizes]

    # Save as multi-resolution ICO
    images[-1].save(
        str(target[0]),
        format='ICO',
        append_images=images[:-1],
        sizes=[(img.width, img.height) for img in images]
    )

    # Also save a PNG preview
    draw_icon(256).save(ICON_PREVIEW)

    print(f"Generated {target[0]} with sizes: {sizes}")
    return None


def build_exe(target, source, env):
    """Build the executable using PyInstaller."""
    # Use absolute paths for icon
    script_dir = Dir('.').abspath
    icon_path = os.path.join(script_dir, ICON_FILE)
    main_path = os.path.join(script_dir, MAIN_SCRIPT)

    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onefile',
        '--windowed',
        f'--icon={icon_path}',
        f'--name={EXE_NAME}',
        '--clean',
        '--noconfirm',
        main_path
    ]
    result = subprocess.run(cmd, shell=False, cwd=script_dir)
    if result.returncode != 0:
        return 1
    print(f"Built {DIST_DIR}/{EXE_NAME}.exe")
    return None


def run_app(target, source, env):
    """Run the application."""
    subprocess.Popen([sys.executable, MAIN_SCRIPT], shell=False)
    return None


# Icon builder
icon_builder = Builder(action=generate_icon)
env.Append(BUILDERS={'IconBuilder': icon_builder})

# EXE builder
exe_builder = Builder(action=build_exe)
env.Append(BUILDERS={'ExeBuilder': exe_builder})

# Run builder
run_builder = Builder(action=run_app)
env.Append(BUILDERS={'RunBuilder': run_builder})

# Installer builder (sign payload -> compile -> sign Setup.exe)
installer_builder = Builder(action=build_installer)
env.Append(BUILDERS={'InstallerBuilder': installer_builder})

# Sign-only builder
sign_builder = Builder(action=sign_only)
env.Append(BUILDERS={'SignBuilder': sign_builder})

# Define targets
icon_target = env.IconBuilder(ICON_FILE, MAIN_SCRIPT)
exe_target = env.ExeBuilder(f'{DIST_DIR}/{EXE_NAME}.exe', [MAIN_SCRIPT, 'nvda_utils.py', ICON_FILE])
run_target = env.RunBuilder('run_marker', MAIN_SCRIPT)

VERSION = read_version()
installer_target = env.InstallerBuilder(
    os.path.join(INSTALLER_OUTPUT_DIR, f'{EXE_NAME}-Setup-{VERSION}.exe'),
    [exe_target, ISS_FILE])
sign_target = env.SignBuilder('sign_marker', [])

# Dependencies
env.Depends(exe_target, icon_target)

# Aliases
env.Alias('icon', icon_target)
env.Alias('build', exe_target)
env.Alias('run', run_target)
env.Alias('installer', installer_target)
env.Alias('sign', sign_target)

# Default target
Default(exe_target)

# Always build targets that run external actions (no reliable file tracking)
env.AlwaysBuild(run_target)
env.AlwaysBuild(installer_target)
env.AlwaysBuild(sign_target)

# Clean targets
Clean(exe_target, [
    'build',
    'dist',
    f'{EXE_NAME}.spec',
    '__pycache__',
    'run_marker'
])
Clean(installer_target, [INSTALLER_OUTPUT_DIR, 'sign_marker'])
