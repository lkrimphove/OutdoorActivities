# Outdoor Activities

- Check out the [demo](https://outdoor-activities.krimphove.site/).
- Check out the whole story on [Medium](https://medium.com/@lukaskrimphove/visualizing-outdoor-activities-with-python-folium-1063baec49a6?sk=533b9ea5c19cbbc7d2eea44a056bc260a6).
- For quick experimenting check out this [Jupyter Notebook](https://github.com/lkrimphove/JupyterNotebooks/blob/main/OutdoorActivities/OutdoorActivities.ipynb).

## How to use
Create a `deploy.tfvars.json` file and change the values to fit your map (you have to change the bucket names, as those have to be globally unique):
```
{
  "input_bucket": "outdoor-activities-input",
  "output_bucket": "outdoor-activities-output",
  "start_latitude": "48.13743",
  "start_longitude": "11.57549",
  "zoom_start": "10"
}
```
Once you've set up the Terraform environment and configured the `main.tf` and `deploy.tfvar.json` files, run the following commands in your terminal:
- Initialize Terraform:

  `terraform init`
- Plan the deployment to see what resources will be created:

  `terraform plan -var-file=„deploy.tfvars.json"`
- Apply the changes to provision the resources:

  `terraform apply -var-file=„deploy.tfvars.json"`

Terraform will show you a summary of the changes that will be made. If everything looks good, type yes to apply the changes. Terraform will now create all the necessary AWS resources for your map. You will find your URL in the console.
Now you are ready to upload your GPX files to the input bucket. Make sure to keep this file structure:
```
input-bucket
├── Hiking
│   ├── Trail Group 1
│   │   ├── Activity_1.gpx
│   │   ├── Activity_2.gpx
│   │   └── ...
│   └── Trail Group 2
│       ├── Activity_1.gpx
│       ├── Activity_2.gpx
│       └── ...
├── ...
└── Skiing
    ├── Trail Group 1
    │   ├── Activity_12.gpx
    │   ├── Activity_13.gpx
    │   └── ...
    └── Trail Group 3
        ├── Activity_14.gpx
        ├── Activity_15.gpx
        └── ...
```

## Support me
If you like my work please consider supporting me by buying me a coffee:

[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/lkrimphove)