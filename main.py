import wx
import wx.adv
import os
import sys
import json
import zipfile
import shutil
import tempfile
import webbrowser
from datetime import datetime
from pathlib import Path

import nvda_utils

VERSION = "1.0"
GITHUB_URL = "https://github.com/slohmaier/NVDAProfileManager"


class NVDAProfileManager(wx.Frame):
    def __init__(self, profile_path=None):
        super().__init__(parent=None, title=f'NVDA Profile Manager v{VERSION}', size=(800, 600))

        self.current_profile_path = None
        self.nvda_path = os.path.join(os.getenv('APPDATA'), 'nvda')

        self.init_ui()
        self._set_icon()
        self.Centre()
        self.Show()

        # Load profile if passed via command line
        if profile_path and os.path.exists(profile_path):
            self.current_profile_path = profile_path
            self.load_profile_info(profile_path)
            self.SetStatusText(f'Opened profile: {os.path.basename(profile_path)}')

    def _set_icon(self):
        """Set the application window icon."""
        # Try to load icon from various locations
        icon_paths = []

        # When running as PyInstaller exe, use the embedded icon
        if getattr(sys, 'frozen', False):
            # Running as compiled exe
            exe_dir = os.path.dirname(sys.executable)
            icon_paths.append(os.path.join(exe_dir, 'icon.ico'))
            # The exe itself can be used as icon source on Windows
            icon_paths.append(sys.executable)
        else:
            # Running from source
            script_dir = os.path.dirname(os.path.abspath(__file__))
            icon_paths.append(os.path.join(script_dir, 'icon.ico'))

        for icon_path in icon_paths:
            if os.path.exists(icon_path):
                try:
                    icon = wx.Icon(icon_path, wx.BITMAP_TYPE_ICO)
                    if icon.IsOk():
                        self.SetIcon(icon)
                        return
                except Exception:
                    pass

    def init_ui(self):
        # Create menu bar
        menubar = wx.MenuBar()
        file_menu = wx.Menu()

        # Menu items
        new_item = file_menu.Append(wx.ID_NEW, '&Create New\tCtrl+N', 'Create new NVDA profile backup')
        open_item = file_menu.Append(wx.ID_OPEN, '&Open\tCtrl+O', 'Open NVDA profile')
        save_item = file_menu.Append(wx.ID_SAVE, '&Save\tCtrl+S', 'Save NVDA profile')
        save_as_item = file_menu.Append(wx.ID_SAVEAS, 'Save &As\tCtrl+Shift+S', 'Save NVDA profile as')
        file_menu.AppendSeparator()
        restore_item = file_menu.Append(wx.ID_ANY, '&Restore Profile', 'Restore NVDA profile from backup')
        file_menu.AppendSeparator()
        exit_item = file_menu.Append(wx.ID_EXIT, 'E&xit\tCtrl+Q', 'Exit application')

        menubar.Append(file_menu, '&File')

        # Tools menu
        tools_menu = wx.Menu()
        register_item = tools_menu.Append(wx.ID_ANY, 'Register File &Type...', 'Associate .nvdaprofile files with this application')
        menubar.Append(tools_menu, '&Tools')

        # Help menu
        help_menu = wx.Menu()
        github_item = help_menu.Append(wx.ID_ANY, '&GitHub Repository', 'Open the GitHub repository in your browser')
        help_menu.AppendSeparator()
        about_item = help_menu.Append(wx.ID_ABOUT, '&About NVDA Profile Manager', 'About this application')
        menubar.Append(help_menu, '&Help')

        self.SetMenuBar(menubar)

        # Bind menu events
        self.Bind(wx.EVT_MENU, self.on_create_new, new_item)
        self.Bind(wx.EVT_MENU, self.on_open, open_item)
        self.Bind(wx.EVT_MENU, self.on_save, save_item)
        self.Bind(wx.EVT_MENU, self.on_save_as, save_as_item)
        self.Bind(wx.EVT_MENU, self.on_restore, restore_item)
        self.Bind(wx.EVT_MENU, self.on_exit, exit_item)
        self.Bind(wx.EVT_MENU, self.on_register_filetype, register_item)
        self.Bind(wx.EVT_MENU, self.on_github, github_item)
        self.Bind(wx.EVT_MENU, self.on_about, about_item)

        # Create main panel
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Add info panel
        info_box = wx.StaticBox(panel, label='Profile Information')
        info_sizer = wx.StaticBoxSizer(info_box, wx.VERTICAL)

        self.info_text = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY, size=(-1, 80))
        info_sizer.Add(self.info_text, 0, wx.EXPAND | wx.ALL, 5)

        vbox.Add(info_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # Add tree control for file listing
        tree_box = wx.StaticBox(panel, label='Profile Contents')
        tree_sizer = wx.StaticBoxSizer(tree_box, wx.VERTICAL)

        self.tree = wx.TreeCtrl(panel, style=wx.TR_DEFAULT_STYLE | wx.TR_HIDE_ROOT)
        tree_sizer.Add(self.tree, 1, wx.EXPAND | wx.ALL, 5)

        vbox.Add(tree_sizer, 1, wx.EXPAND | wx.ALL, 10)

        panel.SetSizer(vbox)

        # Status bar
        self.CreateStatusBar()
        self.SetStatusText('Ready')

    def on_create_new(self, event):
        """Create a new NVDA profile backup"""
        if not os.path.exists(self.nvda_path):
            wx.MessageBox(f'NVDA folder not found at {self.nvda_path}', 'Error', wx.OK | wx.ICON_ERROR)
            return

        # Create temporary .nvdaprofile
        temp_dir = tempfile.gettempdir()
        temp_profile_path = os.path.join(temp_dir, 'temp_nvda_profile.nvdaprofile')

        # Create the profile backup in temp directory
        self.create_profile_backup(temp_profile_path)

        # Set current profile to temp file and load it
        self.current_profile_path = temp_profile_path
        self.load_profile_info(temp_profile_path)
        self.SetStatusText('New profile created (unsaved)')

    def on_open(self, event):
        """Open an existing NVDA profile"""
        wildcard = "NVDA Profile files (*.nvdaprofile)|*.nvdaprofile"
        dlg = wx.FileDialog(self, "Open NVDA Profile",
                           defaultDir=os.path.expanduser("~"),
                           wildcard=wildcard,
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)

        if dlg.ShowModal() == wx.ID_OK:
            path = dlg.GetPath()
            self.current_profile_path = path
            self.load_profile_info(path)
            self.SetStatusText(f'Opened profile: {os.path.basename(path)}')

        dlg.Destroy()

    def on_save(self, event):
        """Save current profile"""
        if not self.current_profile_path:
            wx.MessageBox('No profile to save', 'Error', wx.OK | wx.ICON_ERROR)
            return

        # Check if it's a temp file (unsaved)
        temp_dir = tempfile.gettempdir()
        if self.current_profile_path.startswith(temp_dir):
            # Temp file, need to use Save As
            self.on_save_as(event)
        else:
            # Already saved, just update the file
            self.create_profile_backup(self.current_profile_path)
            self.load_profile_info(self.current_profile_path)
            self.SetStatusText(f'Saved profile: {os.path.basename(self.current_profile_path)}')

    def on_save_as(self, event):
        """Save profile as new file"""
        if not self.current_profile_path:
            wx.MessageBox('No profile to save', 'Error', wx.OK | wx.ICON_ERROR)
            return

        # Ask where to save
        wildcard = "NVDA Profile files (*.nvdaprofile)|*.nvdaprofile"
        dlg = wx.FileDialog(self, "Save NVDA Profile As",
                           defaultDir=os.path.expanduser("~"),
                           wildcard=wildcard,
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)

        if dlg.ShowModal() == wx.ID_OK:
            path = dlg.GetPath()
            if not path.endswith('.nvdaprofile'):
                path += '.nvdaprofile'

            # Copy temp file to new location or create new backup
            temp_dir = tempfile.gettempdir()
            if self.current_profile_path.startswith(temp_dir):
                # Copy temp file to permanent location
                shutil.copy2(self.current_profile_path, path)
            else:
                # Create new backup from current NVDA folder
                self.create_profile_backup(path)

            self.current_profile_path = path
            self.load_profile_info(path)
            self.SetStatusText(f'Saved profile: {os.path.basename(path)}')

        dlg.Destroy()

    def on_restore(self, event):
        """Restore NVDA profile from backup"""
        if not self.current_profile_path:
            wx.MessageBox('Please open a profile first', 'Error', wx.OK | wx.ICON_ERROR)
            return

        # The only real blocker is an open handle on the NVDA folder, which on
        # Windows means NVDA itself is running (it keeps its config files open). A
        # per-file "is this locked" scan was tried before but flagged NVDA's
        # read-only add-on readme files as locked, which they are not; the atomic
        # restore reports any genuine leftover lock on its own.
        if nvda_utils.is_nvda_running():
            dlg = wx.MessageDialog(
                self,
                'NVDA is currently running and must be closed before restoring.\n\n'
                'Close NVDA now?',
                'NVDA Running',
                wx.YES_NO | wx.ICON_WARNING
            )
            close_now = dlg.ShowModal() == wx.ID_YES
            dlg.Destroy()
            if not close_now:
                return
            self.SetStatusText('Closing NVDA...')
            if not nvda_utils.stop_nvda():
                wx.MessageBox(
                    'Could not close NVDA. Please close it manually and try again.',
                    'Error',
                    wx.OK | wx.ICON_ERROR
                )
                return

        # Confirm restore
        dlg = wx.MessageDialog(self,
                              f'This will replace the current NVDA folder at:\n{self.nvda_path}\n\n'
                              'with the opened backup. Your current configuration is kept until the '
                              'new one is safely in place, so a failure leaves it unchanged.\n\n'
                              'Continue?',
                              'Confirm Restore',
                              wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING)

        if dlg.ShowModal() == wx.ID_YES:
            try:
                self.restore_profile(self.current_profile_path)
                self.SetStatusText('Profile restored successfully')

                # Ask if user wants to restart NVDA
                restart_dlg = wx.MessageDialog(
                    self,
                    'Profile restored successfully!\n\nWould you like to start NVDA now?',
                    'Restore Complete',
                    wx.YES_NO | wx.ICON_QUESTION
                )
                if restart_dlg.ShowModal() == wx.ID_YES:
                    if nvda_utils.start_nvda():
                        self.SetStatusText('Profile restored - NVDA started')
                    else:
                        wx.MessageBox(
                            'Could not start NVDA. Please start it manually.',
                            'Warning',
                            wx.OK | wx.ICON_WARNING
                        )
                restart_dlg.Destroy()

            except Exception as e:
                wx.MessageBox(
                    f'Error restoring profile:\n{str(e)}\n\n'
                    'Your existing NVDA configuration was left unchanged.',
                    'Error', wx.OK | wx.ICON_ERROR)

        dlg.Destroy()

    def on_exit(self, event):
        """Exit application"""
        self.Close(True)

    def on_register_filetype(self, event):
        """Register .nvdaprofile file type association"""
        is_registered, location = nvda_utils.is_filetype_registered()

        if is_registered:
            loc_text = "current user" if location == "user" else "system-wide"
            dlg = wx.MessageDialog(
                self,
                f'File type .nvdaprofile is already registered ({loc_text}).\n\n'
                'Would you like to unregister it?',
                'File Type Already Registered',
                wx.YES_NO | wx.ICON_QUESTION
            )
            if dlg.ShowModal() == wx.ID_YES:
                use_hkcu = location == "user"
                success, message = nvda_utils.unregister_filetype(use_hkcu=use_hkcu)
                if success:
                    wx.MessageBox(message, 'Success', wx.OK | wx.ICON_INFORMATION)
                else:
                    wx.MessageBox(message, 'Error', wx.OK | wx.ICON_ERROR)
            dlg.Destroy()
            return

        # Choose registration type
        dlg = wx.SingleChoiceDialog(
            self,
            'Choose registration scope:\n\n'
            '- Current User: No admin required, only affects your account\n'
            '- System-wide: Requires admin, affects all users',
            'Register File Type',
            ['Current User (Recommended)', 'System-wide (Requires Admin)']
        )

        if dlg.ShowModal() == wx.ID_OK:
            use_hkcu = dlg.GetSelection() == 0
            success, message = nvda_utils.register_filetype(use_hkcu=use_hkcu)
            if success:
                wx.MessageBox(message, 'Success', wx.OK | wx.ICON_INFORMATION)
            else:
                wx.MessageBox(message, 'Error', wx.OK | wx.ICON_ERROR)

        dlg.Destroy()

    def on_github(self, event):
        """Open GitHub repository in browser"""
        webbrowser.open(GITHUB_URL)

    def on_about(self, event):
        """Show about dialog"""
        info = wx.adv.AboutDialogInfo()
        info.SetName('NVDA Profile Manager')
        info.SetVersion(VERSION)
        info.SetDescription('A tool to backup and restore NVDA screen reader profiles.\n\n'
                           'Create backups of your NVDA configuration and restore them '
                           'on the same or different computers.')
        info.SetCopyright('(C) 2025 Stefan Lohmaier')
        info.SetWebSite(GITHUB_URL, 'GitHub Repository')
        wx.adv.AboutBox(info)

    def create_profile_backup(self, output_path, show_success=False):
        """Create a backup of the NVDA profile"""
        self.SetStatusText('Creating backup...')

        try:
            # Create descriptor
            descriptor = {
                'username': os.getenv('USERNAME'),
                'computer_name': os.getenv('COMPUTERNAME'),
                'created_date': datetime.now().isoformat(),
                'nvda_path': self.nvda_path
            }

            # Create zip file
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Add descriptor
                zipf.writestr('profile_descriptor.json', json.dumps(descriptor, indent=2))

                # Add all files from NVDA folder
                for root, dirs, files in os.walk(self.nvda_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, self.nvda_path)
                        zipf.write(file_path, arcname)

                    # Preserve empty directories, which the file loop above would
                    # otherwise drop. NVDA relies on several of them existing
                    # (e.g. profiles/, updates/, speechDicts/...).
                    if not files and not dirs and os.path.abspath(root) != os.path.abspath(self.nvda_path):
                        arcname = os.path.relpath(root, self.nvda_path).replace(os.sep, '/') + '/'
                        zipf.writestr(zipfile.ZipInfo(arcname), '')

            if show_success:
                wx.MessageBox(f'Profile backup created successfully!', 'Success', wx.OK | wx.ICON_INFORMATION)

        except Exception as e:
            wx.MessageBox(f'Error creating backup: {str(e)}', 'Error', wx.OK | wx.ICON_ERROR)
            self.SetStatusText('Error creating backup')
            raise

    def restore_profile(self, profile_path):
        """Restore NVDA profile from backup.

        Delegates to nvda_utils.safe_restore, which stages the extraction and swaps
        it in atomically, so a failure leaves the existing configuration intact.
        """
        self.SetStatusText('Restoring profile...')
        nvda_utils.safe_restore(self.nvda_path, profile_path)

    def load_profile_info(self, profile_path):
        """Load and display profile information"""
        try:
            with zipfile.ZipFile(profile_path, 'r') as zipf:
                # Read descriptor
                descriptor_data = zipf.read('profile_descriptor.json')
                descriptor = json.loads(descriptor_data)

                # Display info
                info = f"Username: {descriptor.get('username', 'N/A')}\n"
                info += f"Computer: {descriptor.get('computer_name', 'N/A')}\n"
                info += f"Created: {descriptor.get('created_date', 'N/A')}\n"
                info += f"Original Path: {descriptor.get('nvda_path', 'N/A')}"

                self.info_text.SetValue(info)

                # Populate tree
                self.tree.DeleteAllItems()
                root = self.tree.AddRoot('Profile')

                # Build tree structure
                file_dict = {}
                for item in zipf.namelist():
                    if item == 'profile_descriptor.json':
                        continue

                    parts = item.split('/')
                    current_dict = file_dict

                    for i, part in enumerate(parts):
                        if part not in current_dict:
                            current_dict[part] = {}
                        if i < len(parts) - 1:
                            current_dict = current_dict[part]

                # Add items to tree
                self.add_tree_items(root, file_dict)

        except Exception as e:
            wx.MessageBox(f'Error loading profile: {str(e)}', 'Error', wx.OK | wx.ICON_ERROR)

    def add_tree_items(self, parent, items_dict):
        """Recursively add items to tree"""
        for name, subitems in sorted(items_dict.items()):
            if name:  # Skip empty strings
                item = self.tree.AppendItem(parent, name)
                if subitems:
                    self.add_tree_items(item, subitems)

    def load_current_nvda_profile(self):
        """Load and display current NVDA profile from disk"""
        try:
            # Create descriptor for current profile
            descriptor = {
                'username': os.getenv('USERNAME'),
                'computer_name': os.getenv('COMPUTERNAME'),
                'created_date': datetime.now().isoformat(),
                'nvda_path': self.nvda_path
            }

            # Display info
            info = f"Username: {descriptor.get('username', 'N/A')}\n"
            info += f"Computer: {descriptor.get('computer_name', 'N/A')}\n"
            info += f"Created: {descriptor.get('created_date', 'N/A')}\n"
            info += f"Original Path: {descriptor.get('nvda_path', 'N/A')}"

            self.info_text.SetValue(info)

            # Populate tree with current NVDA folder contents
            self.tree.DeleteAllItems()
            root = self.tree.AddRoot('Profile')

            # Build tree structure from filesystem
            file_dict = {}
            for root_dir, dirs, files in os.walk(self.nvda_path):
                # Get relative path
                rel_path = os.path.relpath(root_dir, self.nvda_path)

                # Build nested dictionary structure
                if rel_path == '.':
                    current_dict = file_dict
                else:
                    parts = rel_path.split(os.sep)
                    current_dict = file_dict
                    for part in parts:
                        if part not in current_dict:
                            current_dict[part] = {}
                        current_dict = current_dict[part]

                # Add files to current level
                for file in files:
                    current_dict[file] = {}

            # Add items to tree
            self.add_tree_items(root, file_dict)

            self.SetStatusText('Loaded current NVDA profile')

        except Exception as e:
            wx.MessageBox(f'Error loading current profile: {str(e)}', 'Error', wx.OK | wx.ICON_ERROR)


def main():
    app = wx.App()

    # Check for command-line argument (file association)
    profile_path = None
    if len(sys.argv) > 1:
        arg_path = sys.argv[1]
        if os.path.exists(arg_path) and arg_path.endswith('.nvdaprofile'):
            profile_path = arg_path

    NVDAProfileManager(profile_path=profile_path)
    app.MainLoop()


if __name__ == '__main__':
    main()
