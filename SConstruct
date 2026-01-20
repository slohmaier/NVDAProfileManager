"""
SCons build file for NVDA Profile Manager

Targets:
    scons           - Build everything (icon + exe)
    scons icon      - Generate icon.ico
    scons build     - Build NVDAProfileManager.exe
    scons run       - Run the application
    scons clean     - Clean build artifacts
"""

import os
import sys
import subprocess
import math

# Environment setup
env = Environment(ENV=os.environ)

# Paths
ICON_FILE = 'icon.ico'
ICON_PREVIEW = 'icon_preview.png'
MAIN_SCRIPT = 'main.py'
EXE_NAME = 'NVDAProfileManager'
DIST_DIR = 'dist'


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

# Define targets
icon_target = env.IconBuilder(ICON_FILE, MAIN_SCRIPT)
exe_target = env.ExeBuilder(f'{DIST_DIR}/{EXE_NAME}.exe', [MAIN_SCRIPT, 'nvda_utils.py', ICON_FILE])
run_target = env.RunBuilder('run_marker', MAIN_SCRIPT)

# Dependencies
env.Depends(exe_target, icon_target)

# Aliases
env.Alias('icon', icon_target)
env.Alias('build', exe_target)
env.Alias('run', run_target)

# Default target
Default(exe_target)

# Always build run target (no actual file to track)
env.AlwaysBuild(run_target)

# Clean targets
Clean(exe_target, [
    'build',
    'dist',
    f'{EXE_NAME}.spec',
    '__pycache__',
    'run_marker'
])
