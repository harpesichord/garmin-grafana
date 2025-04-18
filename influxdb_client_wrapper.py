import os
import logging
from datetime import datetime, timedelta
import pytz

# Environment flag to determine which InfluxDB version to use
INFLUXDB_VERSION = os.getenv("INFLUXDB_VERSION", "2")  # Default to v2

# Common configuration
INFLUXDB_BUCKET_OR_DB = os.getenv("INFLUXDB_V2_BUCKET", os.getenv("INFLUXDB_DATABASE", "garmin"))

# Initialize global client variables
client = None
write_api = None
query_api = None

def initialize_client():
    """Initialize the appropriate InfluxDB client based on INFLUXDB_VERSION"""
    global client, write_api, query_api
    
    try:
        if INFLUXDB_VERSION == "1":
            from influxdb import InfluxDBClient
            from influxdb.exceptions import InfluxDBClientError
            
            # InfluxDB v1 configuration
            INFLUXDB_HOST = os.getenv("INFLUXDB_HOST", "localhost")
            INFLUXDB_PORT = int(os.getenv("INFLUXDB_PORT", 8086))
            INFLUXDB_USERNAME = os.getenv("INFLUXDB_USERNAME", "root")
            INFLUXDB_PASSWORD = os.getenv("INFLUXDB_PASSWORD", "root")
            INFLUXDB_SSL = os.getenv("INFLUXDB_SSL", "false").lower() in ["true", "yes", "1"]
            
            # Initialize InfluxDB v1 client
            client = InfluxDBClient(
                host=INFLUXDB_HOST,
                port=INFLUXDB_PORT,
                username=INFLUXDB_USERNAME,
                password=INFLUXDB_PASSWORD,
                ssl=INFLUXDB_SSL,
                verify_ssl=INFLUXDB_SSL
            )
            client.switch_database(INFLUXDB_BUCKET_OR_DB)
            client.ping()
            logging.info(f"Connected to InfluxDB v1 at {INFLUXDB_HOST}:{INFLUXDB_PORT}")
            
        else:  # Default to v2
            from influxdb_client import InfluxDBClient, Point, WritePrecision
            from influxdb_client.client.write_api import SYNCHRONOUS
            
            # Initialize InfluxDB v2 client
            client = InfluxDBClient.from_env_properties()
            
            # Test the connection
            health = client.health()
            if health.status == "pass":
                logging.info(f"Connected to InfluxDB v{health.version}")
            else:
                raise Exception(f"InfluxDB health check failed: {health.message}")
            
            # Get write API with synchronous write mode
            write_api = client.write_api(write_options=SYNCHRONOUS)
            
            # Get query API for fetching data
            query_api = client.query_api()
            
    except Exception as err:
        logging.error("Unable to connect with influxdb database! Aborted")
        raise Exception(f"InfluxDB connection failed: {str(err)}")


def write_points_to_influxdb(points):
    """Write points to the appropriate InfluxDB version"""
    if not points:
        return
    
    try:
        if INFLUXDB_VERSION == "1":
            client.write_points(points)
            logging.info("Successfully updated InfluxDB v1 database with new points")
        else:  # InfluxDB v2
            from influxdb_client import Point, WritePrecision
            
            # Convert points to the format expected by InfluxDB v2 client
            influx_points = []
            for point in points:
                p = Point(point["measurement"])
                
                # Add tags
                for tag_key, tag_value in point["tags"].items():
                    p = p.tag(tag_key, tag_value)
                
                # Add fields
                for field_key, field_value in point["fields"].items():
                    if field_value is not None:
                        p = p.field(field_key, field_value)
                
                # Add timestamp
                p = p.time(point["time"], WritePrecision.NS)
                
                influx_points.append(p)
            
            # Write points to InfluxDB
            write_api.write(bucket=INFLUXDB_BUCKET_OR_DB, record=influx_points)
            logging.info("Successfully updated InfluxDB v2 database with new points")
            
    except Exception as err:
        logging.error(f"Unable to write to database! {str(err)}")


def get_latest_timestamp_or_default(default_days=7):
    """Get the latest timestamp from InfluxDB or return a default timestamp"""
    try:
        if INFLUXDB_VERSION == "1":
            # InfluxDB v1 query
            result = list(client.query("SELECT * FROM HeartRateIntraday ORDER BY time DESC LIMIT 1").get_points())
            if result:
                return pytz.utc.localize(datetime.strptime(result[0]['time'], "%Y-%m-%dT%H:%M:%SZ"))
        else:
            # InfluxDB v2 query using Flux
            flux_query = f'''
            from(bucket: "{INFLUXDB_BUCKET_OR_DB}")
              |> range(start: -90d)
              |> filter(fn: (r) => r["_measurement"] == "HeartRateIntraday")
              |> sort(columns: ["_time"], desc: true)
              |> limit(n: 1)
            '''
            tables = query_api.query(flux_query)
            
            if tables and len(tables) > 0 and len(tables[0].records) > 0:
                return tables[0].records[0].get_time().astimezone(pytz.timezone("UTC"))
        
        # Return default if no data found
        logging.warning("No previously synced data found in InfluxDB database, defaulting to initial fetching period")
        return (datetime.today() - timedelta(days=default_days)).astimezone(pytz.timezone("UTC"))
        
    except Exception as e:
        logging.error(f"Error querying InfluxDB: {e}")
        return (datetime.today() - timedelta(days=default_days)).astimezone(pytz.timezone("UTC")) 