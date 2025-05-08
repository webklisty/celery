from django import forms
from django.contrib.auth.forms import AuthenticationForm
from ckeditor.widgets import CKEditorWidget
from .models import Campaign, RecipientList
import csv
import io

class CustomAuthenticationForm(AuthenticationForm):
    """Custom login form with styled fields"""
    username = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'}))


class RecipientListForm(forms.ModelForm):
    """Form for creating recipient lists"""
    class Meta:
        model = RecipientList
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'})
        }


class CSVUploadForm(forms.Form):
    """Form for uploading CSV files with recipient data"""
    csv_file = forms.FileField(
        label='CSV File',
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.csv'})
    )
    recipient_list = forms.ModelChoiceField(
        queryset=RecipientList.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def clean_csv_file(self):
        csv_file = self.cleaned_data['csv_file']
        
        # Check if it's a CSV file
        if not csv_file.name.endswith('.csv'):
            raise forms.ValidationError('File must be a CSV file')
        
        # Read and validate the CSV structure
        try:
            csv_file_data = csv_file.read().decode('utf-8')
            csv_io = io.StringIO(csv_file_data)
            reader = csv.DictReader(csv_io)
            
            # Check for required fields
            required_fields = {'name', 'email'}
            if not required_fields.issubset(set(reader.fieldnames)):
                missing = required_fields - set(reader.fieldnames)
                raise forms.ValidationError(f"CSV missing required fields: {', '.join(missing)}")
            
            # Reset the file pointer for later use
            csv_file.seek(0)
            return csv_file
        except Exception as e:
            raise forms.ValidationError(f"Invalid CSV file: {str(e)}")


class CampaignForm(forms.ModelForm):
    """Form for creating and editing campaigns"""
    content = forms.CharField(widget=CKEditorWidget())
    
    class Meta:
        model = Campaign
        fields = [
            'name', 'subject', 'content', 'from_name', 'status',
            'schedule_type', 'scheduled_time', 'recurring_days', 'recipient_list'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'subject': forms.TextInput(attrs={'class': 'form-control'}),
            'from_name': forms.TextInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'schedule_type': forms.Select(attrs={'class': 'form-select'}),
            'scheduled_time': forms.DateTimeInput(
                attrs={'class': 'form-control', 'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M'
            ),
            'recurring_days': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'recipient_list': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['recurring_days'].required = False

    def clean(self):
        cleaned_data = super().clean()
        schedule_type = cleaned_data.get('schedule_type')
        scheduled_time = cleaned_data.get('scheduled_time')
        recurring_days = cleaned_data.get('recurring_days')
        status = cleaned_data.get('status')

        # Automatically set status to 'scheduled' when scheduled_time is provided
        if scheduled_time and status == 'draft':
            cleaned_data['status'] = 'scheduled'
        
        if schedule_type == 'one_time' and not scheduled_time:
            self.add_error('scheduled_time', 'Scheduled time is required for one-time campaigns')
        
        if schedule_type == 'recurring':
            if not scheduled_time:
                self.add_error('scheduled_time', 'Scheduled time is required for recurring campaigns')
            if not recurring_days or recurring_days < 1:
                self.add_error('recurring_days', 'Recurring days must be at least 1 for recurring campaigns')
        
        return cleaned_data
