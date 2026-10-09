import json

from django import forms

from .models import Task


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ["title", "complete"]
        widgets = {"title": forms.TextInput(attrs={"placeholder": "Add new task"})}


class ImportTasksForm(forms.Form):
    tasks_data = forms.CharField(max_length=64000, widget=forms.Textarea)

    def clean_tasks_data(self):
        try:
            titles = json.loads(self.cleaned_data["tasks_data"])
        except json.JSONDecodeError as exc:
            raise forms.ValidationError("Une liste JSON de titres est attendue.") from exc
        if not isinstance(titles, list) or len(titles) > 100:
            raise forms.ValidationError("La liste doit contenir au maximum 100 titres.")
        for title in titles:
            if not isinstance(title, str) or not title.strip() or len(title) > 200:
                raise forms.ValidationError("Chaque titre doit contenir de 1 à 200 caractères.")
        return [title.strip() for title in titles]
