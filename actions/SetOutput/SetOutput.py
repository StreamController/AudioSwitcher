# Import StreamController modules
from GtkHelper.GtkHelper import ComboRow
from src.backend.PluginManager.ActionBase import ActionBase
from src.backend.DeckManagement.DeckController import DeckController
from src.backend.PageManagement.Page import Page
from src.backend.PluginManager.PluginBase import PluginBase

# Import python modules
import os

# Import gtk modules - used for the config rows
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Pango

import pulsectl

class SetOutput(ActionBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.old_state: int = None

    def on_ready(self):
        self.old_state = None
        self.show_state()

    def show_state(self) -> None:
        new_state = self.get_active_sink()
        if new_state == self.old_state:
            return
        self.old_state = new_state

        if new_state == -1:
            self.set_media(media_path=os.path.join(self.plugin_base.PATH, "assets", "speaker.png"), size=0.75)
        else:
            self.set_media(media_path=os.path.join(self.plugin_base.PATH, "assets", "disabled.png"), size=0.75)

    def get_config_rows(self) -> list:
        # Updated model to store: sink name, port name, display name
        self.device_model = Gtk.ListStore.new([str, str, str])  # sink name, port name, display name
        self.device_display_name = Gtk.ListStore.new([str])      # Display name only for the UI
        self.device_row = ComboRow(title=self.plugin_base.lm.get("actions.set-device.device.title"), model=self.device_display_name)

        self.device_cell_renderer = Gtk.CellRendererText(ellipsize=Pango.EllipsizeMode.END, max_width_chars=60)
        self.device_row.combo_box.pack_start(self.device_cell_renderer, True)
        self.device_row.combo_box.add_attribute(self.device_cell_renderer, "text", 0)

        self.load_device_model()

        self.device_row.combo_box.connect("changed", self.on_device_change)

        self.load_config_settings()

        return [self.device_row]

    def load_device_model(self):
        self.device_model.clear()
        self.device_display_name.clear()
        
        with pulsectl.Pulse('set-output') as pulse:
            for sink in pulse.sink_list():
                sink_name = self.get_sink_identifier(sink)
                sink_display_name = self.get_display_name(sink)
                
                if sink_name is None:
                    continue
                    
                # Add the main sink entry first
                main_display_name = sink_display_name
                self.device_model.append([sink_name, "", main_display_name])
                self.device_display_name.append([main_display_name])
                
                # Then add each port/profile as an entry
                if hasattr(sink, 'port_list') and sink.port_list:
                    for port in sink.port_list:
                        if port.name and port.description:
                            port_display_name = f"{sink_display_name} - {port.description}"
                            self.device_model.append([sink_name, port.name, port_display_name])
                            self.device_display_name.append([port_display_name])

    def load_config_settings(self):
        settings = self.get_settings()
        sink_name = settings.get("device")
        port_name = settings.get("port", "")
        
        for i, device in enumerate(self.device_model):
            if device[0] == sink_name and device[1] == port_name:
                self.device_row.combo_box.set_active(i)
                return

        self.device_row.combo_box.set_active(-1)

    def on_device_change(self, combo_box, *args):
        active_idx = combo_box.get_active()
        if active_idx >= 0:
            sink_name = self.device_model[active_idx][0]
            port_name = self.device_model[active_idx][1]
            
            settings = self.get_settings()
            settings["device"] = sink_name
            settings["port"] = port_name
            self.set_settings(settings)

    def get_active_sink(self) -> int:
        settings = self.get_settings()
        device = settings.get("device")
        port = settings.get("port", "")

        with pulsectl.Pulse('set-output') as pulse:
            default_sink = pulse.sink_default_get()
            for sink in pulse.sink_list():
                name = self.get_sink_identifier(sink)
                if name == device and sink.index == default_sink.index:
                    # Check if port matches too if specified
                    if port and hasattr(sink, 'active_port') and sink.active_port:
                        if sink.active_port.name == port:
                            return -1
                    elif not port:  # If no port was specified, just match the sink
                        return -1
        return 0

    def on_key_down(self):
        settings = self.get_settings()
        device_name = settings.get("device")
        port_name = settings.get("port", "")
        
        if device_name is None:
            self.show_error(1)
            return
        
        with pulsectl.Pulse('set-output') as pulse:
            # Find the sink
            target_sink = None
            for sink in pulse.sink_list():
                sink_name = self.get_sink_identifier(sink)
                if sink_name == device_name:
                    target_sink = sink
                    break
            
            if target_sink:
                # Set this sink as default
                pulse.default_set(target_sink)
                
                # If a port is specified, set it
                if port_name and hasattr(target_sink, 'port_list'):
                    for port in target_sink.port_list:
                        if port.name == port_name:
                            pulse.port_set(target_sink, port_name)
                            break

        self.show_state()

    def on_tick(self):
        self.show_state()

    def get_display_name(self, sink) -> str:
        proplist = sink.proplist
        name = (proplist.get("device.product.name") or proplist.get("device.nick") or
                proplist.get("device.description") or sink.name or None)
        description = proplist.get("device.profile.description")
        if description not in ("", None):
            name = f'{name} ({description})'
        return name
    
    def get_sink_identifier(self, sink) -> str:
        proplist = sink.proplist
        return proplist.get("node.name") or sink.name