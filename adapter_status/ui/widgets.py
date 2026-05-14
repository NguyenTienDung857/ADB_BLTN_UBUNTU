import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango

def constrain_label_width(label, max_width_chars=92):
    label.set_line_wrap(True)
    label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
    label.set_max_width_chars(max_width_chars)
    label.set_ellipsize(Pango.EllipsizeMode.NONE)
    return label


def make_text_panel(height, monospace=True, vexpand=False):
    scrolled = Gtk.ScrolledWindow()
    scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
    scrolled.set_size_request(-1, height)
    scrolled.set_hexpand(True)
    scrolled.set_vexpand(vexpand)
    scrolled.get_style_context().add_class("card")

    text_view = Gtk.TextView()
    text_view.set_editable(False)
    text_view.set_cursor_visible(False)
    text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
    text_view.set_monospace(monospace)
    text_view.set_left_margin(8)
    text_view.set_right_margin(8)
    text_view.set_top_margin(8)
    text_view.set_bottom_margin(8)
    scrolled.add(text_view)
    return scrolled, text_view


def set_text_view(text_view, text):
    text = text or ""
    buffer = text_view.get_buffer()
    start_iter, end_iter = buffer.get_bounds()
    if buffer.get_text(start_iter, end_iter, True) == text:
        return
    buffer.set_text(text)
    end_iter = buffer.get_end_iter()
    mark = buffer.create_mark(None, end_iter, False)
    text_view.scroll_mark_onscreen(mark)

