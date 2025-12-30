#!/bin/bash

# Script to clean up WordPress front matter in Hugo posts
# 1. Rename files from YYYY-MM-DD-title.md to YYYY-MM-DD.md
# 2. Remove accelerate_page_layout field
# 3. Replace url: /?p=ID with aliases: [/post/ID]

find content/post -name "*.md" -type f | while read file; do
    echo "Processing: $file"
    
    # Extract the date part (YYYY-MM-DD) from filename
    basename=$(basename "$file")
    dirname=$(dirname "$file")
    
    # Check if filename matches pattern YYYY-MM-DD-*.md
    if [[ $basename =~ ^([0-9]{4}-[0-9]{2}-[0-9]{2})-.+\.md$ ]]; then
        date_part="${BASH_REMATCH[1]}"
        new_filename="${date_part}.md"
        new_filepath="${dirname}/${new_filename}"
        
        echo "  Renaming to: $new_filename"
    else
        # If no date pattern found, keep original filename
        new_filepath="$file"
        echo "  Keeping original filename"
    fi
    
    # Create a temporary file for content processing
    temp_file=$(mktemp)
    
    # Process front matter: remove accelerate_page_layout, convert url to aliases, replace author
    awk '
    BEGIN { 
        in_frontmatter = 0
        skip_next = 0
        url_id = ""
    }
    /^---$/ { 
        in_frontmatter++
        print
        next 
    }
    in_frontmatter == 1 {
        # Replace author admin1045 with alain
        if (/^author: *admin1045/) {
            print "author: alain"
            next
        }
        # Extract ID from url: /?p=1883
        if (/^url: *\/\?p=([0-9]+)/) {
            url_id = $0
            gsub(/^url: *\/\?p=/, "", url_id)
            gsub(/ *$/, "", url_id)
            print "aliases:"
            print "  - /post/" url_id
            next
        }
        # Skip accelerate_page_layout
        if (/^accelerate_page_layout:/) {
            skip_next = 1
            next
        }
        if (skip_next == 1 && /^  -/) {
            next
        } else {
            skip_next = 0
        }
    }
    { print }
    ' "$file" > "$temp_file"
    
    # Move processed file to new location (rename if needed)
    mv "$temp_file" "$new_filepath"
    
    # If we renamed the file, remove the old one
    if [[ "$file" != "$new_filepath" ]]; then
        rm -f "$file"
    fi
done

echo ""
echo "Cleanup complete!"
echo "All posts have been renamed to YYYY-MM-DD.md format"
echo "All url fields converted to aliases"
echo "All accelerate_page_layout fields removed"
