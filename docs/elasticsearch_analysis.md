# Elasticsearch Database Analysis

## Connection Information
- **Host**: https://elk-test.cthb.se:9200
- **Version**: 6.8.23
- **Cluster**: chalmers-elk-test (3 nodes, healthy)
- **Authentication**: Basic auth with credentials from .env

## Key Research Indices

### 1. research-publications-static
- **Documents**: 356,635 publications
- **Size**: 7.8GB (3.9GB primary)
- **Type**: publication

#### Structure Analysis:
- **Complex nested structure** with deep hierarchies
- **Persons**: Array of author objects with:
  - PersonData: Name, ORCID, identifiers, birth year
  - Organizations: Nested affiliations with ROR IDs, Scopus IDs, geographic data
  - Role: Author, Editor, etc.
- **Organizations**: Full organization hierarchy with parents
- **Identifiers**: Multiple ID types (DOI, ORCID, ROR, Scopus, WOS)
- **Language**: ISO codes with English/Swedish names
- **Rich metadata**: Keywords, Abstract, Year, PublicationType

#### Key Fields:
- Title, Abstract, Year, Language
- Persons[].PersonData.DisplayName
- Persons[].PersonData.IdentifierOrcid
- Persons[].Organizations[].OrganizationData.DisplayNameEng
- Organizations[].OrganizationData.Identifiers[].Value (ROR_ID, SCOPUS_AFID)
- Identifiers[].Value (DOI, etc.)
- Keywords, PublicationType

### 2. research-persons-static
- **Documents**: 443,942 persons
- **Size**: 965MB (482.5MB primary)

### 3. research-organizations-static
- **Documents**: 51,189 organizations
- **Size**: 82.3MB (41.1MB primary)

### 4. research-projects-static
- **Documents**: 36,513 projects
- **Size**: 599.5MB (299.7MB primary)

### 5. research-serials-static
- **Documents**: 40,588 serials
- **Size**: 73.1MB (36.5MB primary)

## Sample Query Results

### Publications Query Structure
```json
{
  "Title": "...",
  "Abstract": "...",
  "Year": 2018,
  "Language": {
    "Iso": "eng",
    "NameEng": "English",
    "NameSwe": "engelska"
  },
  "Persons": [
    {
      "Order": 0,
      "Role": {
        "NameEng": "Author",
        "Id": "...",
        "NameSwe": "Författare"
      },
      "PersonData": {
        "DisplayName": "Yan Li",
        "FirstName": "Yan",
        "LastName": "Li",
        "BirthYear": 0,
        "IdentifierOrcid": [],
        "HasPublications": true,
        "HasProjects": false,
        "Identifiers": []
      },
      "Organizations": [
        {
          "OrganizationData": {
            "DisplayNameEng": "Anokiwave Inc.",
            "City": "Austin",
            "Country": "United States",
            "GeoLat": "30.2671530",
            "GeoLong": "-97.7430608",
            "OrganizationTypes": [
              {
                "NameEng": "Private",
                "NameSwe": "Privat"
              }
            ],
            "Identifiers": [
              {
                "Type": {
                  "Value": "SCOPUS_AFID"
                },
                "Value": "121494253"
              },
              {
                "Type": {
                  "Value": "ROR_ID"
                },
                "Value": "https://ror.org/0405mnx93"
              }
            ]
          }
        }
      ]
    }
  ]
}
```

## Complexity Analysis

### Schema Complexity Level: **Very High**
1. **Deep nesting**: 4-5 levels deep in many places
2. **Multiple arrays**: Persons[], Organizations[], Identifiers[]
3. **Rich metadata**: Multiple language variants, full org hierarchies
4. **External identifiers**: DOI, ORCID, ROR, Scopus, WOS integration
5. **Geographic data**: Lat/long coordinates for organizations
6. **Temporal data**: Years, dates, organizational periods

### Query Implications:
- **Nested queries required** for person/organization searches
- **Multiple identifier types** need specialized handling
- **Complex aggregations** needed for relationship analysis
- **Performance considerations** due to document size and nesting

## Tool Design Implications

### Why Specific Tools Make Sense:
1. **Schema encapsulation**: Each domain has unique nested structures
2. **Optimization opportunities**: Domain-specific queries can be hand-tuned
3. **Identifier handling**: Each entity type has different ID patterns
4. **Validation**: Domain-specific input validation and error handling

### Recommended Tool Architecture:
- **Domain-specific core tools** for publications, persons, organizations
- **General analytics tools** for cross-domain operations
- **Identifier resolution tools** for PIDs (DOI, ORCID, ROR)
- **Aggregation tools** for complex analytics

## Performance Considerations

### Large Document Sizes:
- Publications: ~23KB average (7.8GB / 356K docs)
- Complex nested structures increase query complexity
- Field selection crucial for performance

### Indexing Strategy:
- Multiple shards for large indices
- Proper mapping for nested objects
- Keyword fields for exact matching

## External Integration Points

### Persistent Identifiers (PIDs):
- **DOI**: Crossref API integration
- **ORCID**: ORCID public API
- **ROR**: ROR API for organization data
- **Scopus/WOS**: Affiliation IDs for metrics

### API Integration Strategy:
- Use identifiers from ES results to enrich via external APIs
- Cache external API results to avoid rate limiting
- Batch requests where possible

## Next Steps

1. **Analyze other indices** (persons, organizations, projects, serials)
2. **Test complex queries** to understand performance characteristics
3. **Map query patterns** from example_queries.json to actual schema
4. **Design tool interfaces** based on actual data structures
5. **Create documentation** for each tool's schema handling