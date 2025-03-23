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

class ToggleOutput(ActionBase):
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
            self.set_media(media_path=os.path.join(self.plugin_base.PATH, "assets", "speakers.png"), size=0.75)
        elif new_state == 1:
            self.set_media(media_path=os.path.join(self.plugin_base.PATH, "assets", "headphones.png"), size=0.75)
        else:
            self.set_media(media_path=os.path.join(self.plugin_base.PATH, "assets", "none.png"), size=0.75)

    def on_tick(self):
        self.show_state()

    def get_config_rows(self) -> list:
        # Updated model to store: sink name, port name, display name
        self.device_model = Gtk.ListStore.new([str, str, str])  # sink name, port name, display name
        self.device_display_name = Gtk.ListStore.new([str])      # Display name only for the UI

        self.device_A_row = ComboRow(title=self.plugin_base.lm.get("actions.toggle-output.device-a.title"), model=self.device_display_name)
        self.device_cell_renderer = Gtk.CellRendererText(ellipsize=Pango.EllipsizeMode.END, max_width_chars=60)
        self.device_A_row.combo_box.pack_start(self.device_cell_renderer, True)
        self.device_A_row.combo_box.add_attribute(self.device_cell_renderer, "text", 0)

        self.device_B_row = ComboRow(title=self.plugin_base.lm.get("actions.toggle-output.device-b.title"), model=self.device_display_name)
        self.device_cell_renderer = Gtk.CellRendererText()
        self.device_B_row.combo_box.pack_start(self.device_cell_renderer, True)
        self.device_B_row.combo_box.add_attribute(self.device_cell_renderer, "text", 0)

        self.load_device_model()

        self.device_A_row.combo_box.connect("changed", self.on_device_change)
        self.device_B_row.combo_box.connect("changed", self.on_device_change)

        self.load_config_settings()

        return [self.device_A_row, self.device_B_row]
    
    def load_device_model(self):
        self.device_model.clear()
        self.device_display_name.clear()
        
        with pulsectl.Pulse('set-output') as pulse:
            for sink in pulse.sink_list():
                sink_name = self.get_sink_identifier(sink)
                sink_display_name = self.get_device_display_name(sink)
                
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
        device_a_sink = settings.get("device_a")
        device_a_port = settings.get("device_a_port", "")
        device_b_sink = settings.get("device_b")
        device_b_port = settings.get("device_b_port", "")

        self.device_A_row.combo_box.set_active(-1)
        self.device_B_row.combo_box.set_active(-1)
        
        for i, device in enumerate(self.device_model):
            if device[0] == device_a_sink and device[1] == device_a_port:
                self.device_A_row.combo_box.set_active(i)
            if device[0] == device_b_sink and device[1] == device_b_port:
                self.device_B_row.combo_box.set_active(i)

    def on_device_change(self, combo_box, *args):
        device_a_idx = self.device_A_row.combo_box.get_active()
        device_b_idx = self.device_B_row.combo_box.get_active()
        
        if device_a_idx < 0 or device_b_idx < 0:
            return
            
        device_a_sink = self.device_model[device_a_idx][0]
        device_a_port = self.device_model[device_a_idx][1]
        device_b_sink = self.device_model[device_b_idx][0]
        device_b_port = self.device_model[device_b_idx][1]
        
        settings = self.get_settings()
        settings["device_a"] = device_a_sink
        settings["device_a_port"] = device_a_port
        settings["device_b"] = device_b_sink
        settings["device_b_port"] = device_b_port
        self.set_settings(settings)

    def get_active_sink(self) -> int:
        """
        -1 if a
        1 if b
        0 if other
        """
        settings = self.get_settings()
        device_a_sink = settings.get("device_a")
        device_a_port = settings.get("device_a_port", "")
        device_b_sink = settings.get("device_b")
        device_b_port = settings.get("device_b_port", "")

        with pulsectl.Pulse('set-output') as pulse:
            default_sink = pulse.sink_default_get()
            for sink in pulse.sink_list():
                name = self.get_sink_identifier(sink)
                
                # Check if this is device A
                if name == device_a_sink and sink.index == default_sink.index:
                    # Check port if specified
                    if device_a_port and hasattr(sink, 'active_port') and sink.active_port:
                        if sink.active_port.name == device_a_port:
                            return -1
                    elif not device_a_port:  # If no port was specified
                        return -1
                        
                # Check if this is device B
                if name == device_b_sink and sink.index == default_sink.index:
                    # Check port if specified
                    if device_b_port and hasattr(sink, 'active_port') and sink.active_port:
                        if sink.active_port.name == device_b_port:
                            return 1
                    elif not device_b_port:  # If no port was specified
                        return 1
                
        return 0

    def on_key_down(self):
        self.old_state = None
        settings = self.get_settings()
        device_a_sink = settings.get("device_a")
        device_a_port = settings.get("device_a_port", "")
        device_b_sink = settings.get("device_b")
        device_b_port = settings.get("device_b_port", "")
        
        if None in [device_a_sink, device_b_sink]:
            self.show_error(1)
            return
        
        default_sink_result = self.get_active_sink()
        with pulsectl.Pulse('set-output') as pulse:
            if default_sink_result == -1:
                # Device A is selected, switch to device B
                for sink in pulse.sink_list():
                    name = self.get_sink_identifier(sink)
                    if name == device_b_sink:
                        # Set this sink as default
                        pulse.default_set(sink)
                        
                        # If a port is specified, set it
                        if device_b_port and hasattr(sink, 'port_list'):
                            for port in sink.port_list:
                                if port.name == device_b_port:
                                    pulse.port_set(sink, device_b_port)
                                    break
                        break
            else:
                # Either device B or none is selected, switch to device A
                for sink in pulse.sink_list():
                    name = self.get_sink_identifier(sink)
                    if name == device_a_sink:
                        # Set this sink as default
                        pulse.default_set(sink)
                        
                        # If a port is specified, set it
                        if device_a_port and hasattr(sink, 'port_list'):
                            for port in sink.port_list:
                                if port.name == device_a_port:
                                    pulse.port_set(sink, device_a_port)
                                    break
                        break

        self.show_state()

    def get_device_display_name(self, sink) -> str:
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