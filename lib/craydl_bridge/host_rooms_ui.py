"""Read-only Match Rooms preview and choice collection in Revit."""

from __future__ import unicode_literals

from pyrevit import forms
from System.Windows import (
    FontWeights,
    GridLength,
    GridUnitType,
    SystemParameters,
    TextWrapping,
    Thickness,
    VerticalAlignment,
)
from System.Windows.Controls import (
    CheckBox,
    ColumnDefinition,
    ComboBox,
    Grid,
    RowDefinition,
    TextBlock,
)

from craydl_bridge import seed

XAML = """
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Title="Craydl Match Rooms" WindowStartupLocation="CenterOwner"
        ResizeMode="NoResize" ShowInTaskbar="False">
    <Grid Margin="16">
        <Grid.RowDefinitions>
            <RowDefinition Height="Auto"/>
            <RowDefinition Height="3*"/>
            <RowDefinition Height="Auto"/>
            <RowDefinition Height="*"/>
            <RowDefinition Height="Auto"/>
        </Grid.RowDefinitions>
        <StackPanel Margin="0,0,0,8">
            <TextBlock x:Name="job_heading" FontSize="18" FontWeight="Bold" TextWrapping="Wrap"/>
            <TextBlock x:Name="phase_line" TextWrapping="Wrap"/>
            <TextBlock x:Name="counts_line" TextWrapping="Wrap"/>
            <TextBlock x:Name="binding_line" TextWrapping="Wrap"/>
        </StackPanel>
        <ScrollViewer Grid.Row="1" VerticalScrollBarVisibility="Auto"
                      HorizontalScrollBarVisibility="Disabled">
            <StackPanel Margin="0,0,8,0">
                <TextBlock Text="Craydl rooms to decide" FontWeight="Bold"/>
                <StackPanel x:Name="decisions"/>
                <TextBlock Text="Move a Craydl ID" FontWeight="Bold" Margin="0,8,0,0"/>
                <StackPanel x:Name="moves"/>
            </StackPanel>
        </ScrollViewer>
        <StackPanel Grid.Row="2" Margin="0,8,0,4">
            <TextBlock Text="Model rooms with no Craydl room" FontWeight="Bold"/>
            <TextBlock x:Name="model_only_hint" TextWrapping="Wrap" Text="These rooms exist only in the model. Add each one on the job's Rooms tab in Craydl, then run Match Rooms again to link it."/>
        </StackPanel>
        <ScrollViewer Grid.Row="3" VerticalScrollBarVisibility="Auto"
                      HorizontalScrollBarVisibility="Disabled">
            <StackPanel x:Name="model_only"/>
        </ScrollViewer>
        <DockPanel Grid.Row="4" Margin="0,8,0,0" LastChildFill="True">
            <StackPanel DockPanel.Dock="Right" Orientation="Horizontal" VerticalAlignment="Bottom">
                <Button x:Name="apply_button" Content="Apply" MinWidth="84" Padding="8,4"
                        IsDefault="True" Margin="8,0,8,0"/>
                <Button x:Name="cancel_button" Content="Cancel" MinWidth="84" Padding="8,4"/>
            </StackPanel>
            <ScrollViewer VerticalScrollBarVisibility="Auto" MaxHeight="84">
                <TextBlock x:Name="problems" Foreground="Firebrick" TextWrapping="Wrap"/>
            </ScrollViewer>
        </DockPanel>
    </Grid>
</Window>
"""

LINK, CREATE, SKIP = range(3)


def _text(value):
    text = TextBlock()
    text.Text = value
    text.TextWrapping = TextWrapping.Wrap
    return text


def _room_label(model):
    return "%s %s" % (model["number"], model["name"])


def _model_label(model, include_level=False):
    placement = "placed" if seed.is_placed(model) else "not placed"
    if include_level:
        return "%s %s | %s | %s | %s" % (
            model["number"].strip(),
            model["name"],
            model["level"].strip(),
            model["phase"],
            placement,
        )
    return "%s | %s | %s" % (_room_label(model), model["phase"], placement)


class RoomChoice(object):
    def __init__(self, row, free, default):
        self.room = row["room"]
        candidates = row["candidates"]
        candidate_ids = {model["element_id"] for model in candidates}
        self.models = candidates + [
            m for m in free if m["element_id"] not in candidate_ids
        ]
        self.controls = Grid()
        self.controls.Margin = Thickness(0, 6, 0, 6)
        for weight in (2, 2.5, 4):
            column = ColumnDefinition()
            column.Width = GridLength(weight, GridUnitType.Star)
            self.controls.ColumnDefinitions.Add(column)
        for _ in range(2):
            line = RowDefinition()
            line.Height = GridLength.Auto
            self.controls.RowDefinitions.Add(line)

        name = _text(self.room["display_name"])
        name.FontWeight = FontWeights.SemiBold
        self._add(name, 0, 0)

        self.choice = ComboBox()
        for label in ("Link to a model room", "Create a new unplaced room", "Skip"):
            self.choice.Items.Add(label)
        self._add(self.choice, 0, 1)

        self.target = ComboBox()
        self.target.MaxDropDownHeight = 240
        for model in self.models:
            self.target.Items.Add(_model_label(model))
        self._add(self.target, 0, 2)

        self.rename = CheckBox()
        self.rename.Content = _text("Rename the model room to the Craydl name")
        self._add(self.rename, 1, 2)
        reason = _text(seed.TEXT[row["reason"]])
        Grid.SetColumnSpan(reason, 2)
        self._add(reason, 1, 0)

        selection = SKIP
        if default and default["action"] == "link":
            selection = LINK
            self.target.SelectedIndex = next(
                i
                for i, model in enumerate(self.models)
                if model["element_id"] == default["element_id"]
            )
            self.rename.IsChecked = default["rename"]
        elif default:
            selection = CREATE
        self.choice.SelectedIndex = selection
        self.choice.SelectionChanged += self._update_controls
        self._update_controls(None, None)

    def _add(self, control, row, column):
        control.VerticalAlignment = VerticalAlignment.Top
        control.Margin = Thickness(0, 0, 8 if column < 2 else 0, 3)
        Grid.SetRow(control, row)
        Grid.SetColumn(control, column)
        self.controls.Children.Add(control)

    def _update_controls(self, sender, event):
        linking = self.choice.SelectedIndex == LINK
        self.target.IsEnabled = linking
        self.rename.IsEnabled = linking

    def action(self):
        if self.choice.SelectedIndex == LINK:
            index = self.target.SelectedIndex
            return {
                "action": "link",
                "room": self.room,
                "element_id": self.models[index]["element_id"] if index >= 0 else None,
                "rename": bool(self.rename.IsChecked),
            }
        if self.choice.SelectedIndex == CREATE:
            return {"action": "create", "room": self.room}
        return None


class MatchRoomsWindow(forms.WPFWindow):
    def __init__(self, plan, heading, phase, bindings, can_send):
        forms.WPFWindow.__init__(self, XAML, literal_string=True)
        self.Width = min(820, SystemParameters.WorkArea.Width - 32)
        self.Height = min(680, SystemParameters.WorkArea.Height - 32)
        self.plan = plan
        self.result = None
        self.job_heading.Text = heading
        self.phase_line.Text = "Phase for new rooms: " + phase
        self.counts_line.Text = (
            "Already matched: %s | Craydl rooms to decide: %s | "
            "Model rooms with no Craydl room: %s | Starter rooms: %s"
        ) % (
            len(plan["matched"]),
            len(plan["rows"]),
            len(plan["unmatched_model"]),
            len(plan["starters"]),
        )
        if bindings:
            self.binding_line.Text = (
                "Craydl fields to add or complete on Apply: "
                + ", ".join(row["name"] for row in bindings)
            )

        defaults = {
            action["room"]["id"]: action for action in seed.default_actions(plan)
        }
        # The unmatched list excludes rooms taken by default links. Those rooms
        # are still available in every row's picker until an action is confirmed.
        free_by_id = {m["element_id"]: m for m in plan["unmatched_model"]}
        for row in plan["rows"]:
            for model in row["candidates"]:
                free_by_id[model["element_id"]] = model
        free = [free_by_id[key] for key in sorted(free_by_id)]
        self.choices = []
        for row in plan["rows"]:
            choice = RoomChoice(row, free, defaults.get(row["room"]["id"]))
            self.choices.append(choice)
            self.decisions.Children.Add(choice.controls)
        if not self.choices:
            self.decisions.Children.Add(_text("None."))

        self.move_choices = []
        for move in plan["moves"]:
            tick = CheckBox()
            tick.Content = _text(
                "%s: from %s (not placed) to %s"
                % (
                    move["room"]["display_name"],
                    _room_label(move["from"]),
                    _room_label(move["to"]),
                )
            )
            self.move_choices.append((move, tick))
            self.moves.Children.Add(tick)
        if not self.move_choices:
            self.moves.Children.Add(_text("None."))

        self.send_choices = []
        self._model_only_rows(plan, can_send)
        self.apply_button.Click += self._apply
        self.cancel_button.Click += self._cancel

    def _model_only_rows(self, plan, can_send):
        send_ids = set()
        if can_send:
            self.model_only_hint.Text = (
                "Tick a room to add it to this job in Craydl with its name, level and number. "
                "Apply adds it in Craydl and links it here."
            )
            self.tick_all = CheckBox()
            self.tick_all.Content = _text("Tick all rooms below")
            self.tick_all.IsChecked = False
            self.tick_all.IsEnabled = bool(plan["sendable"])
            self.tick_all.Click += self._tick_all
            self.model_only.Children.Add(self.tick_all)
            for model in plan["sendable"]:
                element_id = model["element_id"]
                tick = CheckBox()
                tick.Content = _text(_model_label(model, include_level=True))
                tick.IsChecked = False
                tick.Click += self._update_tick_all
                self.model_only.Children.Add(tick)
                self.send_choices.append((element_id, tick))
                send_ids.add(element_id)
        for model in plan["unmatched_model"]:
            if model["element_id"] not in send_ids:
                label = _model_label(model)
                if can_send:
                    label += " (its name matches a Craydl room; link it or rename it)"
                self.model_only.Children.Add(_text(label))
        if not plan["unmatched_model"]:
            self.model_only.Children.Add(_text("None."))

    def _tick_all(self, sender, event):
        for _, tick in self.send_choices:
            tick.IsChecked = sender.IsChecked

    def _update_tick_all(self, sender, event):
        self.tick_all.IsChecked = all(tick.IsChecked for _, tick in self.send_choices)

    def _apply(self, sender, event):
        actions = [
            action
            for action in (choice.action() for choice in self.choices)
            if action is not None
        ]
        for move, tick in self.move_choices:
            if tick.IsChecked:
                actions.append(
                    {
                        "action": "move",
                        "room": move["room"],
                        "from_element_id": move["from"]["element_id"],
                        "to_element_id": move["to"]["element_id"],
                    }
                )
        actions.extend(
            {"action": "send", "element_id": element_id}
            for element_id, tick in self.send_choices
            if tick.IsChecked
        )
        problems = seed.check_actions(self.plan, actions)
        if problems:
            self.problems.Text = "\n".join(problems)
            return
        self.result = actions
        self.Close()

    def _cancel(self, sender, event):
        self.Close()


def ask(plan, heading, phase, bindings, can_send):
    """Return confirmed actions, or None if the window was closed or cancelled."""
    window = MatchRoomsWindow(plan, heading, phase, bindings, can_send)
    window.show_dialog()
    return window.result
