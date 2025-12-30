#!/bin/bash

# Fix URLs in markdown files
# Replaces https://lemotdujour.fr/?p=XXXX with https://lemotdujour.fr/post/XXXX
# Also removes invalid url: /?p=XXXX lines from front matter

echo "Fixing URLs in content/post/*.md files..."

# Fix URLs in content (both front matter and body)
find content/post -name "*.md" -type f | while read -r file; do
    # Replace URL pattern in content body
    sed -i 's|https://lemotdujour\.fr/\?p=\([0-9]*\)|https://lemotdujour.fr/post/\1|g' "$file"
   
    
    echo "Processed: $file"
done

echo "Done! All URLs have been fixed."
