"""External API extraction with explicit stage outcomes."""
from pathlib import Path

import pandas as pd
import requests
from data_agent.services.etl_files import ETLFileStore, FORMATS
from data_agent.services.etl_results import failed_result, saved_result


def extract_load(url: str, output_folder: str, format: str, *, data_root: Path,
                 filename_stem=None, structured=False):
    # Legacy callers retain their string result; tools also receive a trusted artifact.
    def finish(message, outcome):
        return (message, outcome) if structured else message

    if format not in FORMATS:
        return finish(f"Unsupported format: {format}", failed_result('extraction', 'unsupported_format'))
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        df = pd.json_normalize(data['results'])
    except Exception:
        return finish('Failed to extract data from the external API.',
                      failed_result('extraction', 'extraction_failed'))

    def write(path):
        if format == 'csv':
            df.to_csv(path, index=False)
        elif format == 'json':
            df.to_json(path, orient='records', lines=True)
        else:
            df.to_parquet(path, index=False)
    try:
        stored = ETLFileStore(data_root=data_root).write(source=url, format=format,
                    writer=write, suggested_name=filename_stem, row_count=len(df.index))
    except Exception:
        return finish('Failed to save extracted data: output or metadata could not be finalized. Check storage before retrying.',
                      failed_result('extraction', 'storage_failed'))
    return finish(f"Data successfully extracted and saved to {stored.path}", saved_result(stored, 'extraction'))
