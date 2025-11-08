import wx
import os
import json
import zipfile
import shutil
import tempfile
from datetime import datetime
from pathlib import Path


class NVDAProfileManager(wx.Frame):
    def __init__(self):
        super().__init__(parent=None, title='NVDA Profile Manager', size=(800, 600))

        self.current_profile_path = None
        self.nvda_path = os.path.join(os.getenv('APPDATA'), 'nvda')

        self.init_ui()
        self.Centre()
        self.Show()

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
        self.SetMenuBar(menubar)

        # Bind menu events
        self.Bind(wx.EVT_MENU, self.on_create_new, new_item)
        self.Bind(wx.EVT_MENU, self.on_open, open_item)
        self.Bind(wx.EVT_MENU, self.on_save, save_item)
        self.Bind(wx.EVT_MENU, self.on_save_as, save_as_item)
        self.Bind(wx.EVT_MENU, self.on_restore, restore_item)
        self.Bind(wx.EVT_MENU, self.on_exit, exit_item)

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

        # Ask where to save
        wildcard = "NVDA Profile files (*.nvdaprofile)|*.nvdaprofile"
        dlg = wx.FileDialog(self, "Save NVDA Profile",
                           defaultDir=os.path.expanduser("~"),
                           wildcard=wildcard,
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)

        if dlg.ShowModal() == wx.ID_OK:
            path = dlg.GetPath()
            if not path.endswith('.nvdaprofile'):
                path += '.nvdaprofile'

            self.create_profile_backup(path)
            self.current_profile_path = path
            self.load_profile_info(path)
            self.SetStatusText(f'Created profile: {os.path.basename(path)}')

        dlg.Destroy()

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
        if self.current_profile_path:
            self.create_profile_backup(self.current_profile_path)
            self.SetStatusText(f'Saved profile: {os.path.basename(self.current_profile_path)}')
        else:
            self.on_save_as(event)

    def on_save_as(self, event):
        """Save profile as new file"""
        self.on_create_new(event)

    def on_restore(self, event):
        """Restore NVDA profile from backup"""
        if not self.current_profile_path:
            wx.MessageBox('Please open a profile first', 'Error', wx.OK | wx.ICON_ERROR)
            return

        # Confirm restore
        dlg = wx.MessageDialog(self,
                              f'This will DELETE the current NVDA folder at:\n{self.nvda_path}\n\n'
                              'and replace it with the backup. This cannot be undone!\n\n'
                              'Continue?',
                              'Confirm Restore',
                              wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING)

        if dlg.ShowModal() == wx.ID_YES:
            try:
                self.restore_profile(self.current_profile_path)
                wx.MessageBox('Profile restored successfully!\n\nPlease restart NVDA.',
                            'Success', wx.OK | wx.ICON_INFORMATION)
                self.SetStatusText('Profile restored successfully')
            except Exception as e:
                wx.MessageBox(f'Error restoring profile: {str(e)}', 'Error', wx.OK | wx.ICON_ERROR)

        dlg.Destroy()

    def on_exit(self, event):
        """Exit application"""
        self.Close(True)

    def create_profile_backup(self, output_path):
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

            wx.MessageBox(f'Profile backup created successfully!', 'Success', wx.OK | wx.ICON_INFORMATION)

        except Exception as e:
            wx.MessageBox(f'Error creating backup: {str(e)}', 'Error', wx.OK | wx.ICON_ERROR)
            self.SetStatusText('Error creating backup')

    def restore_profile(self, profile_path):
        """Restore NVDA profile from backup"""
        self.SetStatusText('Restoring profile...')

        # Delete existing NVDA folder
        if os.path.exists(self.nvda_path):
            shutil.rmtree(self.nvda_path)

        # Create NVDA folder
        os.makedirs(self.nvda_path, exist_ok=True)

        # Extract profile
        with zipfile.ZipFile(profile_path, 'r') as zipf:
            for member in zipf.namelist():
                # Skip descriptor file
                if member == 'profile_descriptor.json':
                    continue

                # Extract file
                zipf.extract(member, self.nvda_path)

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
                self.tree.Expand(root)

        except Exception as e:
            wx.MessageBox(f'Error loading profile: {str(e)}', 'Error', wx.OK | wx.ICON_ERROR)

    def add_tree_items(self, parent, items_dict):
        """Recursively add items to tree"""
        for name, subitems in sorted(items_dict.items()):
            if name:  # Skip empty strings
                item = self.tree.AppendItem(parent, name)
                if subitems:
                    self.add_tree_items(item, subitems)


def main():
    app = wx.App()
    NVDAProfileManager()
    app.MainLoop()


if __name__ == '__main__':
    main()
