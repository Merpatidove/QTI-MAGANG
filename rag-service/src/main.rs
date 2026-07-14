// 1. Declare the modules so Rust compiles them
mod models;
mod routes;

use axum::{routing::post, Router};
use std::net::SocketAddr;

#[tokio::main]
async fn main() {
    // 2. Build the Router and attach the route from routes.rs
    let app = Router::new()
        .route("/api/v1/ticket", post(routes::receive_ticket));

    println!("🚀 Inference Service is ONLINE.");
    println!("🛡️ Data Firewall active on http://localhost:3000/api/v1/ticket\n");

    // 3. Bind to port 3000 and start the infinite loop
    let addr = SocketAddr::from(([127, 0, 0, 1], 3000));
    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();
    
    axum::serve(listener, app).await.unwrap();
}