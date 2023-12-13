import csv
import subprocess
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gst', '1.0')
gi.require_version('GstVideo', '1.0')

from gi.repository import Gtk, Gst, GdkX11, GstVideo, Gdk, GLib

class VideoPlayer(Gtk.Window):
    def __init__(self):
        super().__init__(title="VideoTaggingEvents")

        self.init_ui()
        self.init_gstreamer()
        self.set_default_size_and_position()
        self.playback_rate = 1.0  # Tasso di riproduzione iniziale

    def init_ui(self):
        self.set_default_size(800, 450)
        self.connect("key-press-event", self.on_key_press)
        self.video_area = Gtk.DrawingArea()
        self.video_area.connect("draw", self.on_draw)

        # Creazione del layout verticale
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(vbox)

        # Creazione del menu
        menu_bar = Gtk.MenuBar()
        file_menu = Gtk.Menu()
        file_item = Gtk.MenuItem(label="File")
        open_item = Gtk.MenuItem(label="Open")
        close_item = Gtk.MenuItem(label="Close")
        about_item = Gtk.MenuItem(label="About")

        file_item.set_submenu(file_menu)
        file_menu.append(open_item)
        file_menu.append(close_item)
        menu_bar.append(file_item)

        # Creazione del menu "Tag Event"
        tag_event_menu = Gtk.Menu()
        tag_event_item = Gtk.MenuItem(label="Tag Event")
        add_item = Gtk.MenuItem(label="Add")
        show_item = Gtk.MenuItem(label="Show")
        save_item = Gtk.MenuItem(label="Save")

        tag_event_item.set_submenu(tag_event_menu)
        tag_event_menu.append(add_item)
        tag_event_menu.append(show_item)
        tag_event_menu.append(save_item)
        menu_bar.append(tag_event_item)

        export_item = Gtk.MenuItem(label="Export")
        export_item.connect("activate", self.on_export_activate)
        menu_bar.append(export_item)
        menu_bar.append(about_item)
        add_item.connect("activate", self.on_add_activate)
        show_item.connect("activate", self.on_show_activate)
        save_item.connect("activate", self.on_save_activate)

        vbox.pack_start(menu_bar, False, False, 0)

        # Crea un gruppo di acceleratori e aggiungilo alla finestra
        accel_group = Gtk.AccelGroup()
        self.add_accel_group(accel_group)
        add_item.add_accelerator("activate", accel_group, ord('T'), Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE)

        open_item.connect("activate", self.on_open_activate)
        close_item.connect("activate", self.on_close_activate)
        about_item.connect("activate", self.on_about_activate)

        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b'''
        drawingarea {
            background-color: white;
        }
        ''')

        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )


        # Area di visualizzazione video con sfondo bianco
        self.video_area = Gtk.DrawingArea()
        self.video_area.override_background_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(1, 1, 1, 1))
        vbox.pack_start(self.video_area, True, True, 0)

        # Slider inizialmente nascosto
        self.slider = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL)
        self.slider.set_draw_value(False)
        self.slider.connect("value-changed", self.on_slider_changed) #///
        self.slider.set_no_show_all(True)  # Lo slider non verrà mostrato all'inizio
        vbox.pack_start(self.slider, False, True, 0)


        # Aggiungi i bottoni
        self.play_button = Gtk.Button(label="Play")
        self.stop_button = Gtk.Button(label="Stop")
        self.back_button = Gtk.Button(label="Back")
        self.forward_button = Gtk.Button(label="Forward")
        #self.speed_up_button = Gtk.Button(label="++")
        #self.slow_down_button = Gtk.Button(label="--")

        button_box = Gtk.Box(spacing=6)
        button_box.pack_start(self.play_button, True, True, 0)
        button_box.pack_start(self.stop_button, True, True, 0)
        button_box.pack_start(self.back_button, True, True, 0)
        button_box.pack_start(self.forward_button, True, True, 0)
       #button_box.pack_start(self.speed_up_button, True, True, 0)
       #button_box.pack_start(self.slow_down_button, True, True, 0)

        vbox.pack_start(button_box, False, True, 0)

        # Collega i bottoni ai loro handler
        self.play_button.connect("clicked", self.on_play_clicked)
        self.stop_button.connect("clicked", self.on_stop_clicked)
        self.back_button.connect("clicked", self.on_back_clicked)
        self.forward_button.connect("clicked", self.on_forward_clicked)
        #self.speed_up_button.connect("clicked", self.on_speed_up_clicked)
        #self.slow_down_button.connect("clicked", self.on_slow_down_clicked)

    tags_data = []

    def on_export_activate(self, widget):
        # Crea la finestra di dialogo
        export_dialog = Gtk.Dialog("Export Clips", self, 0,
                                (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                                    "Export", Gtk.ResponseType.OK))

        # Crea il layout della finestra
        box = export_dialog.get_content_area()
        
        # Crea un campo di input per il filtro
        self.filter_entry = Gtk.Entry()
        self.filter_entry.set_placeholder_text("Filter by Tag")
        self.filter_entry.connect("changed", self.on_filter_changed)
        box.pack_start(self.filter_entry, False, False, 10)

        # Crea un TreeView per mostrare i dati
        self.create_tags_treeview()
        box.pack_start(self.tags_treeview, True, True, 10)

        export_dialog.show_all()
        response = export_dialog.run()
        if response == Gtk.ResponseType.OK:
            self.export_clips()  # Implementa questa funzione per l'esportazione
        export_dialog.destroy()

    def create_tags_treeview(self):
        # Crea un ListStore con quattro colonne: tag (stringa), prev (int), next (int), frame (int)
        self.tags_liststore = Gtk.ListStore(str, int, int, int)
        self.update_tags_liststore()

        # Crea un TreeView basato sul ListStore
        self.tags_treeview = Gtk.TreeView(model=self.tags_liststore)

        # Aggiungi le colonne al TreeView
        for i, column_title in enumerate(["Tag", "Prev", "Next", "Frame"]):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(column_title, renderer, text=i)
            self.tags_treeview.append_column(column)

    def update_tags_liststore(self):
        # Svuota il ListStore
        self.tags_liststore.clear()

        # Riempilo con i dati di tags_data
        for tag_data in self.tags_data:
            self.tags_liststore.append([tag_data['tag'], tag_data['prev'], tag_data['next'], tag_data['frame']])

    def on_filter_changed(self, widget):
        # Ottieni il testo del filtro
        filter_text = self.filter_entry.get_text().lower()

        # Aggiorna il ListStore in base al filtro
        self.tags_liststore.clear()
        for tag_data in self.tags_data:
            if filter_text in tag_data['tag'].lower():
                self.tags_liststore.append([tag_data['tag'], tag_data['prev'], tag_data['next'], tag_data['frame']])


    def export_clips(self):
        # Assumi che i video siano salvati in un percorso noto e che tu abbia un tool di linea di comando per esportare i segmenti
        base_video_path = "video.mp4"
        output_directory = "."

        for tag_data in self.tags_liststore:
            tag, prev, next, frame = tag_data[0], tag_data[1], tag_data[2], tag_data[3]

            # Calcola i timestamp di inizio e fine per il segmento
            start_time = max(frame - prev * 1000, 0)  # Assicurati che il tempo di inizio non sia negativo
            end_time = frame + next * 1000

            # Genera un nome di file per il segmento esportato
            output_file = f"{output_directory}{tag}_segment.mp4"

            # Usa uno strumento di linea di comando come ffmpeg per esportare il segmento
            # Questo è un esempio e potrebbe dover essere adattato alle tue specifiche esigenze
            command = [
                "ffmpeg", "-i", base_video_path, "-ss", str(start_time), 
                "-to", str(end_time), "-c", "copy", output_file
            ]

            try:
                subprocess.run(command, check=True)
            except subprocess.CalledProcessError as e:
                print(f"Errore nell'esportazione del segmento {tag}: {e}")

            print(f"Segmento esportato: {output_file}")



    def on_key_press(self, widget, event):
        # Gestisce la pressione dei tasti freccia
        keyname = Gdk.keyval_name(event.keyval)
        if keyname == "Left":
            self.move_slider_backward()
        elif keyname == "Right":
            self.move_slider_forward()

    def move_slider_backward(self):
        current_value = self.slider.get_value()
        new_value = max(current_value - 1, 0)  # Sostituisci '1' con l'incremento desiderato
        self.slider.set_value(new_value)

    def move_slider_forward(self):
        current_value = self.slider.get_value()
        max_value = self.slider.get_adjustment().get_upper()
        new_value = min(current_value + 1, max_value)  # Sostituisci '1' con l'incremento desiderato
        self.slider.set_value(new_value)


    def on_add_activate(self, widget):
        # Ottieni la posizione corrente (in nanosecondi) del video dal player
        success, current_pos = self.player.query_position(Gst.Format.TIME)
        if not success:
            print("Impossibile ottenere la posizione corrente del video")
            return

        # Crea una finestra di dialogo
        add_dialog = Gtk.Dialog("Add Tag", self, 0,
            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OK, Gtk.ResponseType.OK))

        # Crea un container all'interno della finestra di dialogo
        content_area = add_dialog.get_content_area()

        # Crea una griglia per organizzare i widget
        grid = Gtk.Grid()
        content_area.add(grid)

        # Crea e aggiungi l'etichetta e l'input per il tag
        tag_label = Gtk.Label("Tag:")
        self.tag_entry = Gtk.Entry()
        grid.attach(tag_label, 0, 0, 1, 1)
        grid.attach_next_to(self.tag_entry, tag_label, Gtk.PositionType.RIGHT, 1, 1)

        # Crea e aggiungi l'etichetta e lo spinner per 'prev'
        prev_label = Gtk.Label("Prev:")
        self.prev_spinner = Gtk.SpinButton()
        self.prev_spinner.set_range(0, 100)  # Imposta un range appropriato
        self.prev_spinner.set_value(5)  # Imposta il valore predefinito
        grid.attach(prev_label, 0, 1, 1, 1)
        grid.attach_next_to(self.prev_spinner, prev_label, Gtk.PositionType.RIGHT, 1, 1)

        # Crea e aggiungi l'etichetta e lo spinner per 'next'
        next_label = Gtk.Label("Next:")
        self.next_spinner = Gtk.SpinButton()
        self.next_spinner.set_range(0, 100)  # Imposta un range appropriato
        self.next_spinner.set_value(5)  # Imposta il valore predefinito
        grid.attach(next_label, 0, 2, 1, 1)
        grid.attach_next_to(self.next_spinner, next_label, Gtk.PositionType.RIGHT, 1, 1)

        # Mostra tutti i widget aggiunti
        add_dialog.show_all()

        # Esegui la finestra di dialogo e salva i risultati se OK viene premuto
        response = add_dialog.run()
        if response == Gtk.ResponseType.OK:
            # Ottieni i valori inseriti
            tag = self.tag_entry.get_text()
            prev = self.prev_spinner.get_value_as_int()
            next = self.next_spinner.get_value_as_int()
            self.tags_data.append({"tag": tag, "prev": prev, "next": next, "pos": current_pos / 1000})
        # Distruggi la finestra di dialogo una volta finito
        add_dialog.destroy()


    def on_show_activate(self, widget):
        # Crea una finestra di dialogo
        show_dialog = Gtk.Dialog("Show Tags", self, 0,
            (Gtk.STOCK_OK, Gtk.ResponseType.OK))

        # Crea un ListStore con quattro colonne: tag (stringa), prev (int), next (int), frame (int)
        liststore = Gtk.ListStore(str, int, int, float)
        for item in self.tags_data:
            liststore.append([item['tag'], item['prev'], item['next'], item['pos']])


        # Crea un TreeView basato sul ListStore
        treeview = Gtk.TreeView(model=liststore)

        # Aggiungi le colonne al TreeView
        for i, column_title in enumerate(["Tag", "Prev", "Next","Pos"]):
            renderer = Gtk.CellRendererText()

            # Rendi la colonna modificabile
            renderer.set_property("editable", True)

            # Aggiungi una funzione di callback per la modifica delle celle
            renderer.connect("edited", self.on_cell_edited, i, liststore)

            column = Gtk.TreeViewColumn(column_title, renderer, text=i)
            treeview.append_column(column)

        # Aggiungi la colonna per il frame
        #frame_renderer = Gtk.CellRendererText()
        #frame_renderer.set_property("editable", True)
        #frame_renderer.connect("edited", self.on_cell_edited, 3, liststore)
        #frame_column = Gtk.TreeViewColumn("Pos", frame_renderer, text=3)
        #treeview.append_column(frame_column)

        # Aggiungi il TreeView alla finestra di dialogo
        show_dialog.get_content_area().add(treeview)
        show_dialog.show_all()

        # Esegui la finestra di dialogo
        show_dialog.run()
        show_dialog.destroy()


    def on_cell_edited(self, widget, path, text, column_index, liststore):
        # Aggiorna il ListStore con il nuovo valore
        liststore[path][column_index] = text

        # Aggiorna la struttura dati tags_data
        if column_index == 0:  # Colonna Tag
            self.tags_data[int(path)]["tag"] = text
        elif column_index == 1:  # Colonna Prev
            self.tags_data[int(path)]["prev"] = int(text)
        elif column_index == 2:  # Colonna Next
            self.tags_data[int(path)]["next"] = int(text)
        elif column_index == 3:  # Colonna Frame
            self.tags_data[int(path)]["pos"] = int(text)

    def on_save_activate(self, widget):
        # Crea una finestra di dialogo per salvare il file
        save_dialog = Gtk.FileChooserDialog("Save File", self,
                                            Gtk.FileChooserAction.SAVE,
                                            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                                            Gtk.STOCK_SAVE, Gtk.ResponseType.OK))

        # Aggiungi un filtro per file CSV
        filter_csv = Gtk.FileFilter()
        filter_csv.set_name("CSV files")
        filter_csv.add_pattern("*.csv")
        save_dialog.add_filter(filter_csv)

        # Imposta l'estensione predefinita
        save_dialog.set_current_name("tags_data.csv")

        response = save_dialog.run()
        if response == Gtk.ResponseType.OK:
            file_name = save_dialog.get_filename()

            # Assicurati che il file abbia l'estensione .csv
            if not file_name.endswith('.csv'):
                file_name += '.csv'

            # Scrivi i dati in un file CSV
            with open(file_name, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.DictWriter(file, fieldnames=["tag", "prev", "next","pos"])
                writer.writeheader()
                for data in self.tags_data:
                    writer.writerow(data)

        # Chiudi la finestra di dialogo
        save_dialog.destroy()

    def get_video_framerate(self):
        # Assumendo che 'self.player' sia il tuo elemento playbin in GStreamer
        video_sink = self.player.get_property("video-sink")

        # Ottieni il pad video
        pad = video_sink.get_static_pad("sink")
        if not pad:
            print("Pad video non trovato")
            return None

        # Interroga il caps del pad
        caps = pad.get_current_caps()
        if not caps or caps.is_empty():
            print("Caps non disponibili")
            return None

        # Estrai la struttura e il frame rate
        structure = caps.get_structure(0)
        framerate = structure.get_fraction("framerate")
        if not framerate:
            print("Frame rate non disponibile")
            return None

        return framerate

    def on_draw(self, widget, cr):
        Gdk.cairo_set_source_rgba(cr, Gdk.RGBA(1, 1, 1, 1))
        cr.paint()
        return False

    def set_default_size_and_position(self):
        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor()
        geometry = monitor.get_geometry()
        screen_width = geometry.width
        screen_height = geometry.height

        # Calcola le dimensioni desiderate (3/4 dello schermo)
        window_width = int(screen_width * 0.75)
        window_height = int(screen_height * 0.75)

        # Imposta le dimensioni della finestra
        self.set_default_size(window_width, window_height)

        # Centra la finestra
        self.set_position(Gtk.WindowPosition.CENTER)


    def init_gstreamer(self):
        Gst.init(None)
        self.player = Gst.ElementFactory.make("playbin", "player")
        self.player.connect("notify::duration", self.on_duration_changed)

        # Imposta Gtk.DrawingArea come sink di GStreamer
        self.video_area.connect("realize", self.on_realize)
        bus = self.player.get_bus()
        bus.add_signal_watch()
        bus.connect("message::eos", self.on_eos)
        bus.connect("message::error", self.on_error)


    def update_slider_position(self):
        # Verifica se il player è in stato di riproduzione
        if self.player.get_state(0).state != Gst.State.PLAYING:
            return False  # Non aggiornare se il video non è in riproduzione

        # Ottieni la posizione corrente del video
        success, position = self.player.query_position(Gst.Format.TIME)
        if not success:
            # Se non è possibile ottenere la posizione, non aggiornare lo slider
            return True  # Ritorna True per continuare a provare ad aggiornare

        # Aggiorna la posizione dello slider senza emettere il segnale 'value-changed'
        self.slider.handler_block_by_func(self.on_slider_changed)
        self.slider.set_value(position / Gst.SECOND)
        self.slider.handler_unblock_by_func(self.on_slider_changed)

        return True  # Continua ad aggiornare lo slider



    def on_duration_changed(self, player, duration):
        # Aggiorna il range massimo dello slider quando la durata del video è conosciuta
        dur_int = self.player.query_duration(Gst.Format.TIME)[1]
        self.slider.set_range(0, dur_int / Gst.SECOND)


    def on_realize(self, widget):
        window = widget.get_window()
        win_id = window.get_xid()
        self.player.set_window_handle(win_id)

    def on_open_activate(self, widget):
        #dialog = Gtk.FileChooserDialog("Open File", self, Gtk.FileChooserAction.OPEN,
        #                               ("Cancel", Gtk.ResponseType.CANCEL, "Open", Gtk.ResponseType.OK))

        dialog = Gtk.FileChooserDialog(
            title="Open File",
            parent=self,
            action=Gtk.FileChooserAction.OPEN
        )
        dialog.add_buttons(
            "Cancel", Gtk.ResponseType.CANCEL,
            "Open", Gtk.ResponseType.OK
        )

        response = dialog.run()

    
        if response == Gtk.ResponseType.OK:
            uri = dialog.get_filename()
            self.player.set_property("uri", Gst.filename_to_uri(uri))
            self.player.set_state(Gst.State.PAUSED)  # Mette in pausa dopo il primo frame
            self.update_slider_range()  # Aggiorna e mostra lo slider
            print(self.get_video_framerate())
        dialog.destroy()



    def update_slider_range(self):
        # Ottiene la durata del video e aggiorna lo slider
        self.player.get_state(Gst.CLOCK_TIME_NONE)
        success, duration = self.player.query_duration(Gst.Format.TIME)
        if success:
            self.slider.set_range(0, duration / Gst.SECOND)
            self.slider.show()  # Mostra lo slider


    def on_slider_changed(self, slider):
        # Chiamato quando lo slider viene spostato
        # Metti in pausa il video e aggiorna la posizione
        self.player.set_state(Gst.State.PAUSED)
        self.play_button.set_label("Play")

        seek_time = slider.get_value()
        seek_time_ns = seek_time * Gst.SECOND
        self.player.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT, seek_time_ns)

    def on_close_activate(self, widget):
        Gtk.main_quit()

    def on_about_activate(self, widget):
        dialog = Gtk.MessageDialog(self, 0, Gtk.MessageType.INFO, Gtk.ButtonsType.OK, "Ciao mondo")
        dialog.run()
        dialog.destroy()

    def on_eos(self, bus, msg):
        self.player.set_state(Gst.State.READY)

    def on_error(self, bus, msg):
        err, debug = msg.parse_error()
        print("Error: %s" % err, debug)
        self.player.set_state(Gst.State.READY)


    def on_play_clicked(self, button):
        # Controlla lo stato corrente del video
        state = self.player.get_state(0).state

        if state == Gst.State.PLAYING:
            # Se il video è in riproduzione, mettilo in pausa
            self.player.set_state(Gst.State.PAUSED)
            button.set_label("Play")
        else:
            # Se il video è in pausa o fermo, riprendi la riproduzione
            self.player.set_state(Gst.State.PLAYING)
            button.set_label("Pause")
        
        GLib.timeout_add(500, self.update_slider_position)


    def on_stop_clicked(self, button):
        # Ferma il video
        self.player.set_state(Gst.State.READY)  # o Gst.State.NULL, a seconda delle necessità

        # Imposta la label del bottone "Play/Break/Continue" su "Play"
        self.play_button.set_label("Play")

        # Riporta lo slider all'inizio
        self.slider.set_value(0)

    def on_back_clicked(self, button):
        # Ottieni la posizione attuale del video
        success, current_position = self.player.query_position(Gst.Format.TIME)
        if success:
            # Calcola la nuova posizione (non meno di 0)
            new_position = max(current_position - (5 * Gst.SECOND), 0)
            
            # Sposta il video alla nuova posizione
            self.player.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT, new_position)

            # Aggiorna la posizione dello slider
            self.slider.set_value(new_position / Gst.SECOND)


    def on_forward_clicked(self, button):
        # Ottieni la posizione attuale del video
        success, current_position = self.player.query_position(Gst.Format.TIME)
        if success:
            # Ottieni la durata totale del video per assicurarsi di non superarla
            success, duration = self.player.query_duration(Gst.Format.TIME)
            if success:
                # Calcola la nuova posizione senza superare la durata totale
                new_position = min(current_position + (5 * Gst.SECOND), duration)

                # Sposta il video alla nuova posizione
                self.player.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT, new_position)

                # Aggiorna la posizione dello slider
                self.slider.set_value(new_position / Gst.SECOND)

    def on_slow_down_clicked(self, button):
        # Diminuisci il tasso di riproduzione
        self.playback_rate = max(self.playback_rate / 2, 0.1)  # limite minimo 0.1x

        # Applica il nuovo tasso di riproduzione
        self.set_playback_rate(self.playback_rate)


    def on_speed_up_clicked(self, button):
        # Aumenta il tasso di riproduzione
        self.playback_rate = min(self.playback_rate * 2, 10)  # limite massimo 10x

        # Applica il nuovo tasso di riproduzione
        self.set_playback_rate(self.playback_rate)

    def set_playback_rate(self, rate):
        # Ottieni la posizione corrente del video
        success, current_position = self.player.query_position(Gst.Format.TIME)
        if not success or current_position == Gst.CLOCK_TIME_NONE:
            return  # Non procedere se la posizione non è disponibile o non è definita

        # Preparare i valori per la funzione seek
        seek_flags = Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT
        start_type = Gst.SeekType.SET
        stop_type = Gst.SeekType.SET

        # Effettuare la seek
        success = self.player.seek(rate, Gst.Format.TIME, seek_flags,
                                start_type, current_position,
                                stop_type, current_position)
        if not success:
            print("Seek non riuscita")

        # Riavvia la riproduzione se necessario
        if self.player.get_state(0).state == Gst.State.PAUSED:
            self.player.set_state(Gst.State.PLAYING)


app = VideoPlayer()
app.connect("destroy", Gtk.main_quit)
app.show_all()
Gtk.main()
