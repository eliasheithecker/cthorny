import logging

import json

from utils import Context
from models.paths import WorkingFiles


log = logging.getLogger(__name__)


def flatten_ptr_records(ctx: Context) -> None:
    output_file = ctx.workingPathOf(WorkingFiles.ALL_SCANNER_PTR_RECORDS_FLAT)
    if not ctx.force_reload and output_file.exists():
        log.info("Flattened PTR records already exist, skipping step")
        return
    
    input_file = ctx.workingPathOf(WorkingFiles.ALL_SCANNER_PTR_RECORDS_RAW)
    
    flatten_ptr(str(input_file), str(output_file))
    
    log.info("Flattened PTR records saved to %s", output_file)
    
    
def flatten_ptr(input_path, output_path):
    
    with open(input_path, 'r') as infile, open(output_path, 'w') as outfile:
        for line in infile:
            if line.strip():
                record = json.loads(line)
                
                # Extract IP address
                ip = record.get('name', '')
                
                # Navigate to status and answer
                ptr_result = record.get('results', {}).get('PTR', {})
                status = ptr_result.get('status', '')
                
                # Extract hostname if status is NOERROR and answers exist
                hostname = ''
                if status == 'NOERROR':
                    answers = ptr_result.get('data', {}).get('answers', [])
                    hostname = answers[0].get('answer', '') if answers else ''
                    # Remove trailing dot from hostname
                    hostname = hostname.rstrip('.')
                
                # Write flattened record for every IP
                flat_record = {
                    'ip': ip,
                    'hostname': hostname,
                    'status': status
                }
                outfile.write(json.dumps(flat_record, separators=(',', ':')) + '\n')
    
    print(f"Flattened PTR records written to {output_path}")