SPARK MEMBERSHIP → ODOO MIGRATION
===================================

This folder contains SAMPLE CSV files showing the expected format
for importing Spark Membership data into Dojo Manager (Odoo).

FILES
-----
  sample_members.csv      — Member profiles (name, email, belt rank, stage)
  sample_contracts.csv    — Membership plans and contract dates
  sample_attendance.csv   — Class check-in history
  sample_leads.csv        — Prospects and leads pipeline
  sample_payments.csv     — Payment history (creates Odoo invoices)
  sample_belt_history.csv — Belt promotion records

HOW TO EXPORT FROM SPARK
-------------------------
1. Log into your Spark account
2. Go to:  Reports → Export  (or  Members → Export)
3. Download each section as CSV
4. Rename columns to match the headers in these sample files
   (or the wizard will try to detect them automatically)

HOW TO IMPORT INTO ODOO
------------------------
1. Open Dojo Manager in Odoo
2. Go to:  Configuration → Import from Spark
3. Upload each CSV file in the correct tab
4. Tick "Dry run" first to preview without saving
5. Click "Run Import"
6. Review the summary, then run again without Dry run

COLUMN MAPPING
--------------
The wizard accepts multiple column name variations from Spark exports.
See the info boxes in each tab for accepted column names.

NOTES
-----
- Members are matched by email address
- Duplicate records are skipped unless "Overwrite existing" is checked
- Portal login accounts (password: member123) are created for new members
  if "Create portal login accounts" is checked
- Payments create posted account.move (invoice) records in Odoo Accounting
- Belt history updates the member's CURRENT belt rank (not a log)
