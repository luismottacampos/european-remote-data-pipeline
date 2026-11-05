import pyarrow as pa

JOB_DATA_SCHEMA = pa.schema([
    # Unique identifiers
    pa.field('id', pa.string(), nullable=False),          # UUID v4 (primary key)
    pa.field('url_hash', pa.string(), nullable=False),     # SHA-256 of normalised URL

    # Source fields
    pa.field('url', pa.string(), nullable=False),
    pa.field('raw_title', pa.string(), nullable=False),

    # Extraction metadata
    pa.field('raw_employer', pa.string()),
    pa.field('employer', pa.string()),
    pa.field('raw_content', pa.large_string()),
    pa.field('errors', pa.list_(pa.string())),

    # LLM-extracted content (nested)
    pa.field('content', pa.struct([
        pa.field('company_name', pa.string()),
        pa.field('department_name', pa.string()),
        pa.field('team_name', pa.string()),
        pa.field('date_posted', pa.string()),
        pa.field('job_context', pa.large_string()),

        pa.field('compensation', pa.struct([
            pa.field('pay_range', pa.large_string()),  # JSON string
            pa.field('benefits', pa.list_(pa.string()))
        ])),

        pa.field('responsibilities', pa.list_(pa.string())),

        pa.field('qualifications', pa.struct([
            pa.field('required', pa.list_(pa.string())),
            pa.field('additional', pa.list_(pa.string()))
        ]))
    ]))
])
