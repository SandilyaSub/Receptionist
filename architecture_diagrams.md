# Receptionist AI - Architecture Diagrams

This document contains Mermaid diagrams for the Receptionist AI system architecture.

## 1. System Overview

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#bbf', 'primaryBorderColor': '#333', 'lineColor': '#333'}}}%%
flowchart TD
    A[Customer] -->|Calls| B[Exotel]
    B -->|WebSocket| C[Receptionist AI]
    C -->|Process Audio| D[Google Gemini AI]
    C -->|Store Data| E[(Supabase DB)]
    C -->|Send Notifications| F[WhatsApp]
    F -->|Confirmation| A
    F -->|Summary| G[Business Owner]
```

## 2. Call Flow Sequence

```mermaid
sequenceDiagram
    participant C as Customer
    participant E as Exotel
    participant R as Receptionist AI
    participant G as Gemini AI
    participant S as Supabase
    
    C->>E: Places Call
    E->>R: WebSocket Connection
    R->>S: Get Tenant Config
    R->>G: Initialize Session
    
    loop Audio Processing
        C->>E: Speak
        E->>R: Audio Data
        R->>G: Process Audio
        G-->>R: AI Response
        R-->>E: Response Audio
    end
    
    E->>R: End Call
    R->>S: Save Transcript
    R->>R: Analyze Call
    R->>S: Store Analysis
    R->>WhatsApp: Send Notifications
```

## 3. Multi-Tenant Architecture

```mermaid
graph TD
    subgraph "Tenant Repository"
        B[Bakery]
        S[Salon]
    end
    
    subgraph "Server"
        W[WebSocket Server]
        T[Transcript Analyzer]
        A[Action Service]
        N[Notification Service]
    end
    
    subgraph "Database"
        TC[Tenant Configs]
        CD[Call Details]
        NO[Notifications]
    end
    
    B & S -->|Load Configuration| W
    W <--> TC
    W --> T --> A --> N
    N -->|Send| W
    CD --> A
    A --> CD & NO
```

## 4. Database Schema

```mermaid
erDiagram
    TENANT_CONFIGS ||--o{ CALL_DETAILS : has
    CALL_DETAILS ||--o{ NOTIFICATIONS : triggers
    
    TENANT_CONFIGS {
        bigint id PK
        text tenant_id UK
        text tenant_name
        jsonb call_type_schema
        boolean is_active
        timestamptz created_at
    }
    
    CALL_DETAILS {
        bigint id PK
        text call_sid UK
        text tenant FK
        jsonb transcript
        text call_type
        jsonb critical_call_details
        timestamptz created_at
    }
    
    NOTIFICATIONS {
        bigint id PK
        text call_sid FK
        text recipient
        text status
        jsonb payload
        timestamptz created_at
    }
```

## 5. Notification Flow

```mermaid
flowchart LR
    A[Call Ends] --> B[Analyze Transcript]
    B --> C[Generate Messages]
    C --> D[Send to Customer]
    C --> E[Send to Business]
    
    subgraph "Message Generation"
        C -->|Template| F[Customer Message]
        C -->|Template| G[Owner Message]
    end
    
    D --> H[Customer WhatsApp]
    E --> I[Owner WhatsApp]
    
    style A fill:#f9f,stroke:#333
    style H,I fill:#bfb,stroke:#333
```

These diagrams provide a clear visualization of the system architecture and data flow. The Mermaid syntax has been simplified to ensure compatibility across different renderers.
