from operator import itemgetter
from collections import OrderedDict

import urwid
import formatter

MAX_COLUMN_WIDTH = 60

class TaskTable(object):

    def __init__(self, task_config, report, tasks, on_select=None):
        self.task_config = task_config
        self.report = report
        self.tasks = tasks
        self.on_select = on_select
        self.formatter_defaults = formatter.Defaults(task_config)
        self.columns = OrderedDict()
        self.rows = []
        self.sort()
        self.set_column_metadata()
        self.build_rows()
        # TODO: Make this optional based on Taskwarrior config setting.
        self.clean_empty_columns()
        self.reconcile_column_width_for_label()
        self.build_table()

    def sort(self):
        for column, order, collate in reversed(self.report['sort']):
            if order and order == 'descending':
                self.tasks = sorted(self.tasks, key=itemgetter(column), reverse=True)
            else:
                self.tasks = sorted(self.tasks, key=itemgetter(column))

    def set_column_metadata(self):
        for idx, column_formatter in enumerate(self.report['columns']):
            parts = column_formatter.split('.')
            name = parts[0]
            formatter_class_name = ''.join([p.capitalize() for p in parts])
            formatter_class = getattr(formatter, formatter_class_name)
            self.columns[name] = {
                'label': self.report['labels'][idx],
                'formatter': formatter_class,
                'width': 0,
            }

    def build_rows(self):
        for task in self.tasks:
            row_data = {}
            for column, metadata in list(self.columns.items()):
                current = metadata['width']
                formatted_value = metadata['formatter'](task, self.formatter_defaults).format(task[column])
                new = len(formatted_value) if formatted_value else 0
                if new > current and current < MAX_COLUMN_WIDTH:
                    self.columns[column]['width'] = new < MAX_COLUMN_WIDTH and new or MAX_COLUMN_WIDTH
                row_data[column] = formatted_value
            self.rows.append(TaskRow(task, row_data))

    def clean_empty_columns(self):
        self.columns = {c:m for c,m in list(self.columns.items()) if m['width'] > 0}

    def reconcile_column_width_for_label(self):
        for column, metadata in list(self.columns.items()):
            label_len = len(metadata['label'])
            if metadata['width'] < label_len:
                self.columns[column]['width'] = label_len

    def build_table(self):
        self.contents = [SelectableRow(self.columns, task, on_select=self.on_select) for task in self.rows]
        self.listbox = TaskListBox(urwid.SimpleFocusListWalker(self.contents))

        list_header = urwid.Columns([(metadata['width'] + 2, urwid.Text(metadata['label'], align='left')) for column, metadata in list(self.columns.items())])
        self.header = urwid.AttrMap(list_header, 'list-header')

class TaskRow():
    def __init__(self, task, data):
        self.task = task
        self.data = data
        self.uuid = self.task['uuid']

class SelectableRow(urwid.WidgetWrap):
    """Wraps 'urwid.Columns' to make it selectable.
    This class has been slightly modified, but essentially corresponds to this class posted on stackoverflow.com:
    https://stackoverflow.com/questions/52106244/how-do-you-combine-multiple-tui-forms-to-write-more-complex-applications#answer-52174629"""

    def __init__(self, columns, row, *, align="left", on_select=None, space_between=2):
        self.task = row.task
        self.uuid = row.uuid

        self._columns = urwid.Columns([(metadata['width'], urwid.Text(row.data[column], align=align)) for column, metadata in list(columns.items())],
                                       dividechars=space_between)
        self._focusable_columns = urwid.AttrMap(self._columns, '', 'reveal focus')

        # Wrap 'urwid.Columns'.
        super().__init__(self._focusable_columns)

        # A hook which defines the behavior that is executed when a specified key is pressed.
        self.on_select = on_select

    def __repr__(self):
        return "{}(contents='{}')".format(self.__class__.__name__,
                                          self.contents)

    def selectable(self):
        return True

    def keypress(self, size, key):
        if self.on_select:
            key = self.on_select(self, size, key)
        return key

    def set_contents(self, contents):
        # Update the list record inplace...
        self.contents[:] = contents

        # ... and update the displayed items.
        for t, (w, _) in zip(contents, self._columns.contents):
            w.set_text(t)

class TaskListBox(urwid.ListBox):
    """Maps task list shortcuts to default ListBox class.
    """
    def keypress(self, size, key):
        """Overrides ListBox.keypress method.
        """
        if key in ['j', ' ']:
            self.keypress(size, 'down')
            return True
        if key in ['ctrl f']:
            self.keypress(size, 'page down')
            return True
        if key in ['k']:
            self.keypress(size, 'up')
            return True
        if key in ['ctrl b']:
            self.keypress(size, 'page up')
            return True
        # TODO: Can make 'g' 'gg'?
        if key in ['g', '0']:
            self.set_focus(0)
            return True
        if key in ['G']:
            self.set_focus(len(self.body) - 1)
            self.set_focus_valign('bottom')
            return True
        # TODO: This is wrong, should go to middle line on screen.
        if key in ['M']:
            self.set_focus(self.focus_position)
            self.set_focus_valign('middle')
            return True
        return super().keypress(size, key)

