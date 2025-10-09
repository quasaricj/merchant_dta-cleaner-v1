# Merchant Data Cleaning Rules

## Purpose
This document defines the complete business rules for cleaning credit card merchant transaction data. These rules solve the problem where credit card companies (like Mastercard/Visa) receive messy, inconsistent merchant names from acquirers, POS systems, and aggregators, and need to standardize them for fraud detection, dispute resolution, and consumer transparency.

## Business Problem Context

Credit card merchant names are often unclear because:
- **Merchant Name Source**: Sent by merchant's acquiring bank, not standardized
- **Legal vs Brand Names**: "Fresh Cafe" appears as "FRESH CFE #8272 SAN JOSE CA 409"  
- **Legacy Systems**: Character limits, bad formatting, auto-generated IDs
- **No Enforcement**: Card networks relay data as-is to avoid legal disputes
- **Aggregator Noise**: PayPal, Stripe, Uber Eats add prefixes like "PAYPAL*UBER EATS 800-123-4567"

## Core Processing Workflow

### Six-Step Search Logic
For each merchant row, perform searches in this exact order, **stopping only when both cleaned merchant name AND working website are found**:

1. **Merchant + address + city + country**
2. **Merchant + city + country** 
3. **Merchant + city**
4. **Merchant + country**
5. **Merchant only**
6. **Merchant + street**

### Pre-Processing Rules
- **Payment Aggregator Removal**: Strip aggregator names (PayPal, Stripe, Razorpay, PhonePe, GooglePay, Uber Eats, etc.) from anywhere in merchant string
- **Special Character Cleaning**: Remove all special characters, emojis, Unicode symbols from final merchant name
- **Evidence Documentation**: Always mention in evidence if aggregator was removed and from where

### Missing Input Data Handling
- If address/city/country columns are partially blank: Run available search patterns only
- If ALL input columns blank (including merchant string): Leave all output columns blank
- Never treat partial data as "unable to clean"

## Output Field Rules

### Cleaned Merchant Name
- **Format**: Proper capitalization (first letter capital, rest lowercase) - "Starbucks" not "STARBUCKS"
- **Source**: Must be found on internet via search results, never AI-generated
- **Franchise Handling**: Use main brand only - "KFC New Delhi" becomes "KFC"
- **If Not Found**: Leave blank

### Website
- **Requirement**: Must be official, working, live business website
- **Format**: Clean main domain only - "https://tiendasneto.com.mx" not "https://tiendasneto.com.mx/tiendas"
- **Validation**: Actually verify site opens and contains business content (not parked, for sale, under construction)
- **Security**: Accept both HTTP and HTTPS
- **Redirects**: Accept final redirected domain if valid
- **If Not Found**: Leave blank

### Social Media Links  
- **Primary Rule**: Only populate if NO website found
- **If Website Found**: Always leave social media blank
- **Format**: Direct profile URLs only
- **Selection**: Choose best location/address match if multiple profiles found
- **Requirements**: Must contain business info or address details
- **If Not Found**: Leave blank

### Logo Filename
- **If Website Found**: Use domain name + ".png" (e.g., "example.com" → "example.png")
- **If Social Only**: Use cleaned merchant name without spaces + ".png" (e.g., "Reliance Retail" → "RelianceRetail.png")  
- **If Neither Found**: Leave blank

### Remarks
- **No Merchant Found**: "NA"
- **Merchant Found, No Website**: "website unavailable"
- **Merchant Found, Social Only**: "website unavailable"
- **All Other Cases**: Leave blank

### Evidence
- **Content**: Detailed explanation of search process, which query succeeded, validation steps taken
- **Language**: Simple English, non-technical, audit-ready
- **Requirements**: Based only on actual search results, never AI hallucinations
- **Aggregator Documentation**: Mention if/where aggregator was removed

### Evidence Links
- **Format**: Direct clickable link to search result page that provided evidence
- **Length**: No trimming required, full URLs acceptable
- **Purpose**: Allow auditor to verify decision

### Cost Per Row
- **Calculation**: Actual API costs incurred for that specific row's processing
- **Tracking**: Count real searches, AI calls, website validations performed
- **Currency**: Always in USD

## Edge Case Decision Matrix

### Business Validation

| Scenario | Action | Evidence Note |
|----------|--------|---------------|
| Multiple similar businesses found | Accept closest match | "Chose closest match among X similar businesses" |
| Address/city slightly different | Accept if franchise/chain | "Address differs but validated as franchise location" |
| Only aggregator sites (Yelp, TripAdvisor) | Accept best match | "Evidence only from review sites, chose best match" |
| Marked as closed/permanently closed | **Reject** | "Business marked as permanently closed" |
| Franchise/chain location | Accept | Use main brand name only |
| Historical/archived page only | **Reject** | "Only archived evidence found" |

### Website Validation

| Scenario | Action | Evidence Note |
|----------|--------|---------------|
| Multiple candidate websites | Choose most similar to merchant name | "Selected X over Y due to closer brand match" |
| Redirects to parent company | Accept if dedicated business site | "Redirects to parent but maintains business focus" |
| Subpage of mall/directory | **Reject** | "Found only as subpage, not official site" |
| Foreign domain (.co.uk for US business) | Accept if location evidence exists | "Foreign domain but confirmed local presence" |
| Social media page as "website" | **Reject** (use in social field) | "Found social profile, not official website" |

### Social Media Validation

| Scenario | Action | Evidence Note |
|----------|--------|---------------|
| Multiple profiles found | Choose best location match | "Selected profile matching city/address" |
| Unverified but location-matched | Accept | "Unverified but matches business location" |
| No address/business info | **Reject** | "Profile lacks business address details" |
| Personal profile of owner | **Reject** | "Personal profile, not business page" |
| Verified with many followers but no address | Accept | "Verified profile with business branding" |

## Quality Assurance Rules

### Consistency Requirements
- **Identical Input**: Same merchant string + location must produce identical results
- **Deterministic Logic**: No random AI variations for same data
- **Field Dependencies**: Website presence determines social media population

### Evidence from External Sources
- **News/Press Releases**: Accept and note source type
- **Government/Legal Documents**: Accept and note authority
- **Third-party Business Directories**: Accept and note aggregator source

### Data Corruption Handling
- **Corrupted Merchant Strings**: Process normally, don't skip
- **Non-alpha Characters**: Clean but continue processing
- **Very Short Strings**: Process normally, don't reject

## System Performance Rules

### Large File Processing
- **Capacity**: Handle minimum 300,000 rows per job
- **Data Persistence**: No data loss on system shutdown or errors
- **Cost Protection**: Preserve API cost investments through checkpointing
- **Error Handling**: Pause and show status, allow resume
- **Progress Tracking**: Real-time row completion updates

### Cost Optimization
- **Early Stopping**: Stop search sequence when both merchant name and website validated
- **API Efficiency**: Track and charge only actual API calls made per row
- **Batch Processing**: Optimize for large datasets without sacrificing accuracy

## Compliance and Audit

### Documentation Standards
- Every decision must be traceable to search results
- Evidence must be human-readable and audit-ready
- All edge cases must be explicitly documented
- Cost tracking must be transparent and accurate

### Quality Control
- No AI hallucinations in output fields
- All populated fields must have search result backing
- Consistent handling of identical input data
- Clear escalation path for manual review cases