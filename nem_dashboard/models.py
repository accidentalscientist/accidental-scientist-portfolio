from django.db import models

class FuelDataUpload(models.Model):
    csv_file = models.FileField(upload_to='fuel_data_uploads/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Upload on {self.uploaded_at}"

class FuelGenerationData(models.Model):
    timestamp = models.DateTimeField()
    state = models.CharField(max_length=10)
    fuel_type = models.CharField(max_length=50)
    supply_mw = models.FloatField()

    def __str__(self):
        return f"{self.timestamp} | {self.state} | {self.fuel_type} | {self.supply_mw} MW"
