use std::fs;

fn main() {
    // 1. Read the file from your hard drive into memory
    println!("📖 Reading RAG Manual...");
    let content = fs::read_to_string("RAG_Manual.md")
        .expect("❌ Failed to read RAG_Manual.md. Make sure it's in the data-pipeline folder!");
    
    println!("✅ Successfully read {} bytes.\n", content.len());

    // 2. Split the giant text into smaller blocks
    // Every time Rust sees a newline followed by "# SOP-", it cuts the text.
    let blocks: Vec<&str> = content.split("\n# SOP-").collect();
    
    // The first block (index 0) is just the intro text before the first SOP.
    // We use [1..] to skip it and only keep the actual SOPs.
    let sop_blocks = &blocks[1..]; 

    println!("✅ Found {} SOP entries.\n", sop_blocks.len());
    println!("--- LIST OF SOPs ---");

    // 3. Loop through each block and extract the ID and Title
    for (i, block) in sop_blocks.iter().enumerate() {
        // Get the very first line of the block.
        let first_line = block.lines().next().unwrap_or("Unknown Title");
        
        // Split that first line at the colon to separate ID from Title
        let parts: Vec<&str> = first_line.splitn(2, ": ").collect();
        
        if parts.len() == 2 {
            let id = parts[0].trim();      // Example: "DB-001"
            let title = parts[1].trim();   // Example: "MySQL Connection Timeout"
            
            // {:2} is a formatting trick to align the numbers nicely
            println!("{:2}. SOP-{}: {}", i + 1, id, title);
        } else {
            println!("{:2}. {}", i + 1, first_line);
        }
    }
}