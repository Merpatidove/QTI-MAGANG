// =====================================================================
// FILE PURPOSE:
// This file acts as the "Table of Contents" for the `clients` folder.
// 
// ARCHITECTURE NOTE:
// While the `routes` folder handles INBOUND traffic (HTTP requests coming 
// into our server from the AI Agent), the `clients` folder handles OUTBOUND 
// traffic (HTTP requests our server makes to external services like the 
// Qdrant database or the Mac Mini Inference server).
// =====================================================================

// Tell the Rust compiler to look for a file named `qdrant.rs` in this folder.
// The `pub` keyword makes the code inside `qdrant.rs` visible to the rest 
// of the application (specifically, so our `routes/query.rs` can use it).
pub mod qdrant;