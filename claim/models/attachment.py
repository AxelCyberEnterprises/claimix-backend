import os
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import FileExtensionValidator
from django.core.exceptions import ValidationError

User = get_user_model()

def validate_file_size(value):
    """
    Validate that the file size is not larger than 10MB.
    """
    limit = 10 * 1024 * 1024  # 10MB
    if value.size > limit:
        raise ValidationError('File too large. Size should not exceed 10MB.')

def claim_attachment_upload_path(instance, filename):
    """
    Generate upload path for claim attachments.
    Format: claims/attachments/{claim_id}/{timestamp}_{filename}
    """
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    _, ext = os.path.splitext(filename)
    return f'claims/attachments/{instance.claim.claim_id}/{timestamp}_{instance.claim.claim_id}{ext}'

class ClaimAttachment(models.Model):
    """
    Model for storing file attachments related to claims.
    """
    # Allowed file types
    ALLOWED_EXTENSIONS = [
        'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',  # Documents
        'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'webp',  # Images
        'txt', 'rtf', 'csv', 'json', 'xml',                   # Text files
        'zip', 'rar', '7z', 'tar', 'gz'                      # Archives
    ]
    
    claim = models.ForeignKey(
        'claim.Claim',
        on_delete=models.CASCADE,
        related_name='attachments',
        help_text="The claim this attachment belongs to"
    )
    
    file = models.FileField(
        upload_to=claim_attachment_upload_path,
        validators=[
            FileExtensionValidator(allowed_extensions=ALLOWED_EXTENSIONS),
            validate_file_size
        ],
        help_text="The uploaded file"
    )
    
    original_filename = models.CharField(
        max_length=255,
        help_text="Original filename of the uploaded file"
    )
    
    file_type = models.CharField(
        max_length=50,
        help_text="File type/category (e.g., 'document', 'image', 'spreadsheet')"
    )
    
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Optional description of the attachment"
    )
    
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_attachments',
        help_text="User who uploaded the file"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Claim Attachment'
        verbose_name_plural = 'Claim Attachments'
    
    def save(self, *args, **kwargs):
        # Set the original filename if not already set
        if not self.original_filename and hasattr(self.file, 'name'):
            self.original_filename = self.file.name
        
        # Set file type based on extension
        if not self.file_type and hasattr(self.file, 'name'):
            ext = os.path.splitext(self.file.name)[1].lower().replace('.', '')
            if ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'webp']:
                self.file_type = 'image'
            elif ext in ['pdf']:
                self.file_type = 'document'
            elif ext in ['doc', 'docx', 'rtf', 'txt']:
                self.file_type = 'document'
            elif ext in ['xls', 'xlsx', 'csv']:
                self.file_type = 'spreadsheet'
            elif ext in ['zip', 'rar', '7z', 'tar', 'gz']:
                self.file_type = 'archive'
            else:
                self.file_type = 'other'
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.original_filename} (Claim: {self.claim.claim_id})"
    
    @property
    def file_size(self):
        """
        Returns the file size in a human-readable format.
        """
        if self.file and self.file.storage.exists(self.file.name):
            size_bytes = self.file.size
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size_bytes < 1024.0:
                    return f"{size_bytes:.1f} {unit}"
                size_bytes /= 1024.0
            return f"{size_bytes:.1f} TB"
        return "0 B"
