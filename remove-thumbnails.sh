#!/bin/bash

# Script to remove WordPress thumbnail/resized images and keep only original images
# WordPress creates multiple sizes like: image-150x150.jpg, image-300x200.jpg, image-768x432.jpg
# This script keeps only the original: image.jpg

echo "Removing WordPress thumbnail and resized images..."
echo "Keeping only original full-size images"
echo ""

removed_count=0
kept_count=0

# Find all image files in wp-content/uploads
find static/wp-content/uploads -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.gif" -o -iname "*.bmp" \) | while read file; do
    filename=$(basename "$file")
    
    # Check if filename contains size pattern like -150x150, -300x200, -1024x768, etc.
    # Pattern: -[digits]x[digits] before the extension
    if [[ $filename =~ -[0-9]+x[0-9]+\. ]]; then
        echo "Removing: $file"
        rm -f "$file"
        ((removed_count++))
    else
        echo "Keeping: $file"
        ((kept_count++))
    fi
done

echo ""
echo "Cleanup complete!"
echo "Note: Counts are approximate due to subshell execution"
echo "Run 'find static/wp-content/uploads -type f | wc -l' to see total remaining files"
