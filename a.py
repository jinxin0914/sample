import json
import logging
from datetime import datetime
import psycopg2
from smb.SMBConnection import SMBConnection
import tempfile
import os
import sys
import yaml
from typing import Dict, Any

# Configure logging - optimized for Databricks platform, use standard output only
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # Keep only StreamHandler, remove FileHandler
    ]
)
logger = logging.getLogger(__name__)

def load_configuration(environment) -> Dict[str, Any]:
    """Loads environment-specific YAML configuration."""
    config_files = {
        'DEV': 'application_dev.yaml',
        'UAT': 'application_uat.yaml',
        'PROD': 'application_prd.yaml'
    }

    config_file = config_files.get(environment, 'application_dev.yaml')
    if environment not in config_files:
        logger.warning(f"Environment {environment} not found, using DEV as default")

    with open(config_file, 'r') as file:
        config = yaml.safe_load(file)
    logger.info(f"Loaded configuration for environment: {environment} from {config_file}")
    return config

# Load configuration at script start
APP_CONFIG = load_configuration("DEV")

# Extract configuration values
CREATED_BY = APP_CONFIG.get('created_by', 'sync_script')
UPDATED_BY = APP_CONFIG.get('updated_by', 'sync_script')
SMB_CONFIG: Dict[str, Any] = APP_CONFIG.get('smb', {})
S3_CONFIG = APP_CONFIG.get('s3', {})
S3_BUCKET = S3_CONFIG.get('s3_bucket', '')
S3_PREFIX = S3_CONFIG.get('s3_prefix', '')
S3_VOLUME_PATH = S3_CONFIG.get('volume_path', '')
DB_CONFIG: Dict[str, Any] = APP_CONFIG.get('database', {})

# Log loaded configuration summary
logger.info(f"Configuration loaded for {os.environ.get('ENVIRONMENT', 'DEV').upper()} environment:")
logger.info(f"- SMB Server: {SMB_CONFIG.get('server_name', 'Not configured')}")
logger.info(f"- S3 Bucket: {S3_BUCKET}")
logger.info(f"- S3 Prefix: {S3_PREFIX}")
logger.info(f"- S3 Volume Path: {S3_VOLUME_PATH}")
logger.info(f"- Database: {DB_CONFIG.get('dbname', 'Not configured')}")

def connect_to_smb():
    """Connect to Windows shared folder"""
    try:
        conn = SMBConnection(
            SMB_CONFIG['username'],
            SMB_CONFIG['password'],
            SMB_CONFIG['client_name'],
            SMB_CONFIG['server_name'],
            domain=SMB_CONFIG['domain'],
            use_ntlm_v2=True
        )
        connected = conn.connect(SMB_CONFIG['server_ip'], 139)
        if not connected:
            logger.error("Failed to connect to SMB server")
            return None
        logger.info("Successfully connected to SMB server")
        return conn
    except Exception as e:
        logger.exception("Error connecting to SMB server")
        return None

def load_json_data(json_file):
    """Load JSON data file"""
    try:
        with open(json_file, 'r') as f:
            data = json.load(f)
            logger.info(f"Successfully loaded JSON data, containing {len(data)} run records")
            return data
    except Exception as e:
        logger.exception("Error loading JSON file")
        return None

def update_database(run_data):
    """Update model_run and model_output tables in the database"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Insert into model_run table
        cursor.execute("""
            INSERT INTO sfp.model_run
            (run_id, exercise, cycle, vendor, created_by, updated_by, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (run_id) DO NOTHING
        """, (
            run_data["run_id"],
            run_data["exercise"],
            run_data["cycle"],
            run_data["vendor"],
            CREATED_BY,
            UPDATED_BY,
            datetime.now(),
            datetime.now()
        ))
        
        # Insert into model_output table
        for output in run_data["outputs"]:
            s3_file_path = f"{S3_PREFIX}{run_data['run_id']}/{output['file_name']}"
            cursor.execute("""
                INSERT INTO sfp.model_output
                (run_id, file_path, file_name, scenario, s3_path, created_by, updated_by, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (run_id, file_name) DO NOTHING
            """, (
                run_data["run_id"],
                output["win_file_path"],
                output["file_name"],
                output["scenario"],
                s3_file_path,
                CREATED_BY,
                UPDATED_BY,
                datetime.now(),
                datetime.now()
            ))
        
        conn.commit()
        logger.info(f"Successfully updated database: run_id {run_data['run_id']}, containing {len(run_data['outputs'])} output files")
        cursor.close()
        conn.close()
    except Exception as e:
        logger.exception("Error updating database")
        if 'conn' in locals() and conn is not None:
            conn.rollback()
            conn.close()

def upload_to_s3(smb_conn, run_data):
    """Upload files from Windows shared folder to AWS S3"""
    try:
        from pyspark.dbutils import DBUtils
        from pyspark.sql import SparkSession
        
        spark = SparkSession.builder.getOrCreate()
        dbutils = DBUtils(spark)
        
        success_count = 0
        skipped_count = 0
        
        for output in run_data["outputs"]:
            try:
                # Build source file path and target S3 path
                smb_file_path = f"{output['win_file_path']}/{output['file_name']}"
                s3_file_path = f"{S3_PREFIX}{run_data['run_id']}/{output['file_name']}"
                s3_full_path = f"{S3_VOLUME_PATH}/{s3_file_path}"
                
                # Check if file already exists in S3
                if dbutils.fs.ls(s3_full_path):
                    logger.info(f"File already exists in S3, skipping: {s3_file_path}")
                    skipped_count += 1
                    continue
                
                logger.info(f"Processing file: {smb_file_path} -> {s3_full_path}")
                
                # Create temporary file and download SMB file
                with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                    temp_path = temp_file.name
                    smb_conn.retrieveFile(SMB_CONFIG['share_name'], smb_file_path, temp_file)
                
                # Ensure S3 target directory exists
                target_dir = os.path.dirname(s3_full_path)
                dbutils.fs.mkdirs(target_dir)
                
                # Copy file to S3
                dbutils.fs.cp(f"file://{temp_path}", s3_full_path)
                
                # Delete temporary file
                os.unlink(temp_path)
                
                logger.info(f"File successfully uploaded to S3: {s3_file_path}")
                success_count += 1
            except Exception as e:
                logger.exception(f"Error uploading file {output.get('file_name', 'Unknown')}")
        
        logger.info(f"File upload for Run ID {run_data['run_id']} completed: "
                   f"{success_count} uploaded, {skipped_count} skipped, "
                   f"{len(run_data['outputs']) - success_count - skipped_count} failed")
    except Exception as e:
        logger.exception("Error uploading to S3")

def main():
    """Main function to coordinate the entire synchronization process"""
    start_time = datetime.now()
    logger.info(f"Starting synchronization task: {start_time}")
    
    # Load JSON data
    json_data = load_json_data("data.json")
    if not json_data:
        logger.error("Failed to load JSON data, terminating execution")
        return
    
    # Connect to SMB server
    smb_conn = connect_to_smb()
    if not smb_conn:
        logger.error("Failed to connect to SMB server, terminating execution")
        return
    
    # Process each run record
    total_runs = len(json_data)
    successful_runs = 0
    
    for i, run_data in enumerate(json_data, 1):
        try:
            logger.info(f"Processing {i}/{total_runs} run record: run_id {run_data.get('run_id', 'Unknown')}")
            
            # Update database
            update_database(run_data)
            
            # Upload files to S3
            upload_to_s3(smb_conn, run_data)
            
            successful_runs += 1
        except Exception as e:
            logger.exception(f"Error processing run_id {run_data.get('run_id', 'Unknown')}")
    
    # Close SMB connection
    smb_conn.close()
    
    # Record execution statistics
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    logger.info(f"Synchronization task completed: {successful_runs}/{total_runs} run records processed successfully")
    logger.info(f"Total execution time: {duration:.2f} seconds")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.exception("Critical error during execution")
        sys.exit(1)
