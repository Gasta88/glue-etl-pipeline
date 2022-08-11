# How to visualize pipeline logs.

This part of the project leverage few tools:

- _docker-compose_ to setup a local deployment where the logs will be stored.
- _ElasticSearch_ to store the logs as documents.
- _Kibana_ to create visualizations and a dashboard.

The idea is to have a graphical representation of the logs gathered during a workflow run.

Make sure to have Docker installed on your machine to run this part of the project. Some data are already available inside `/data_observability/data` but the dashboard should be already set up
once the deployment is started.

## Instructions:

Open a terminal in this folder where you find this README.md file:

1. Run `docker-compose up -d`
2. Connect to [http://localhost:5601/](http://localhost:5601/)
3. If you navigate to **Dashboard** or **Visualizations** on the left panel, you should see all the necessary elements.
4. Remember to toggle the timestamp selector to discover all the metrics available.
5. Run `docker-compose down` once you have finished.

If no data or visualization is available, follow these steps:

1. Run `docker-compose up -d`
2. Connect to [http://localhost:5601/](http://localhost:5601/)
3. If you navigate to **Integrations** on the left panel, you can search for _Upload data from file_. The add-on will help you to import the data.
4. Take note of the index id from the URL bar once imported. Replace the old index id form `data_observability/exports/export.json` to align the visualizations.
5. To import the objects, go to **Management > Saved Objects** and choose to import the `data_observability/exports/export.json` file.
6. Run `docker-compose down` once you have finished.
