# Receptionist AI System Architecture

This document provides detailed flow diagrams for the Receptionist AI system architecture.

## Complete System Flow

```mermaid
graph TB
    %% Main Components
    Customer([Customer])
    Exotel[Exotel Telephony]
    WebSocket[WebSocket Server]
    Gemini[Google Gemini AI]
    Supabase[(Supabase Database)]
    ActionService[Action Service]
    WhatsApp[WhatsApp Notification]
    
    %% Call Flow
    Customer -->|Places call| Exotel
    Exotel -->|WebSocket connection| WebSocket
    WebSocket -->|1. Fetch tenant config| Supabase
    WebSocket -->|2. Initialize conversation| Gemini
    
    %% Conversation Loop
    subgraph ConversationLoop [Real-time Conversation]
        direction TB
        AudioIn[Customer Audio]
        ProcessAudio[Process Audio]
        GenerateResponse[Generate Response]
        AudioOut[AI Response Audio]
        
        AudioIn --> ProcessAudio
        ProcessAudio --> GenerateResponse
        GenerateResponse --> AudioOut
        AudioOut --> AudioIn
    end
    
    WebSocket --- ConversationLoop
    
    %% Post-Call Processing
    Exotel -->|End call| WebSocket
    WebSocket -->|Save transcript| Supabase
    WebSocket -->|Trigger analysis| TranscriptAnalyzer
    
    subgraph PostCallProcessing [Post-Call Processing]
        direction TB
        TranscriptAnalyzer[Transcript Analyzer]
        FetchCallDetails[Fetch Call Details]
        ProcessActions[Process Actions]
        GenerateNotifications[Generate Notifications]
        SendNotifications[Send Notifications]
        
        TranscriptAnalyzer -->|Analyze transcript| Supabase
        FetchCallDetails -->|Get call data| Supabase
        ProcessActions -->|Determine actions| GenerateNotifications
        GenerateNotifications -->|Create messages| SendNotifications
    end
    
    WebSocket --> PostCallProcessing
    PostCallProcessing --> ActionService
    ActionService -->|Send notifications| WhatsApp
    WhatsApp -->|Confirmation| Customer
    WhatsApp -->|Summary| Business([Business Owner])
    
    %% Database Interactions
    Supabase -->|Tenant configs| WebSocket
    Supabase -->|Call type schema| TranscriptAnalyzer
    Supabase -->|Call details| ActionService
    
    %% Styling
    classDef external fill:#f9f,stroke:#333,stroke-width:2px;
    classDef core fill:#bbf,stroke:#333,stroke-width:2px;
    classDef database fill:#bfb,stroke:#333,stroke-width:2px;
    classDef process fill:#fbb,stroke:#333,stroke-width:2px;
    
    class Customer,Business,Exotel,WhatsApp external;
    class WebSocket,TranscriptAnalyzer,ActionService core;
    class Supabase database;
    class ConversationLoop,PostCallProcessing process;
    class Gemini external;
```

## Component Interactions

### WebSocket Server Flow

```mermaid
sequenceDiagram
    participant Exotel
    participant Server as WebSocket Server
    participant Gemini
    participant DB as Supabase
    
    Exotel->>Server: Connect (WebSocket)
    Server->>Server: Create GeminiSession
    Server->>DB: Fetch tenant config
    
    Exotel->>Server: Send 'start' message with tenant_id
    Server->>Server: Initialize TranscriptManager
    Server->>Gemini: Initialize conversation with tenant prompt
    
    par Audio Processing
        Exotel->>Server: Stream audio data
        Server->>Gemini: Send audio chunks
        Gemini->>Server: Generate responses
        Server->>Exotel: Stream response audio
    and Keep-Alive
        Server->>Exotel: Send periodic keep-alive messages
    end
    
    Exotel->>Server: End call (disconnect)
    Server->>Server: Cleanup session
    Server->>DB: Save transcript
    Server->>DB: Fetch Exotel call details
    Server->>DB: Store call details
    Server->>Server: Trigger transcript analysis
```

### Transcript Analysis Flow

```mermaid
sequenceDiagram
    participant Bridge as WebSocket Bridge
    participant Analyzer as Transcript Analyzer
    participant DB as Supabase
    participant Gemini
    
    Bridge->>Analyzer: analyze_transcript(transcript, tenant)
    Analyzer->>DB: Fetch call type schema for tenant
    DB->>Analyzer: Return call_type_schema
    
    Analyzer->>Analyzer: Create universal prompt
    Analyzer->>Gemini: Generate content (analyze transcript)
    Gemini->>Analyzer: Return analysis (JSON)
    
    Analyzer->>Analyzer: Validate response
    Analyzer->>DB: Update call_details with analysis
    Analyzer->>Bridge: Return analysis result
```

### Action Service Flow

```mermaid
sequenceDiagram
    participant Bridge as WebSocket Bridge
    participant Action as Action Service
    participant DB as Supabase
    participant WhatsApp as WhatsApp Service
    participant MSG91 as MSG91 Provider
    
    Bridge->>Action: process_call_actions(call_sid, tenant_id)
    Action->>DB: Fetch call details
    DB->>Action: Return call details & analysis
    
    Action->>Action: Determine notification recipients
    
    par Customer Notification
        Action->>WhatsApp: prepare_customer_notification(call_details)
        WhatsApp->>Gemini: generate_ai_message(call_type, details)
        Gemini->>WhatsApp: Return AI-generated message
        WhatsApp->>WhatsApp: Format with template
        WhatsApp->>MSG91: Send WhatsApp message
        MSG91->>Action: Return delivery status
        Action->>DB: Log notification
    and Owner Notification
        Action->>WhatsApp: prepare_owner_notification(call_details)
        WhatsApp->>Gemini: generate_ai_message(call_type, details)
        Gemini->>WhatsApp: Return AI-generated message
        WhatsApp->>MSG91: Send WhatsApp message
        MSG91->>Action: Return delivery status
        Action->>DB: Log notification
    end
```

## Multi-Tenant Architecture

```mermaid
graph TD
    subgraph TenantRepository [Tenant Repository]
        direction TB
        Bakery[/bakery/]
        Saloon[/saloon/]
        
        subgraph BakeryFiles [Bakery Files]
            direction TB
            BakeryPrompts[/prompts/]
            BakeryInputFiles[/input_files/]
            BakeryAssistant[assistant.txt]
            BakeryAnalyzer[analyzer.txt]
            BakeryMenu[menu.txt]
            
            BakeryPrompts --> BakeryAssistant
            BakeryPrompts --> BakeryAnalyzer
            BakeryInputFiles --> BakeryMenu
        end
        
        subgraph SaloonFiles [Saloon Files]
            direction TB
            SaloonPrompts[/prompts/]
            SaloonInputFiles[/input_files/]
            SaloonAssistant[assistant.txt]
            SaloonAnalyzer[analyzer.txt]
            SaloonServices[services.txt]
            
            SaloonPrompts --> SaloonAssistant
            SaloonPrompts --> SaloonAnalyzer
            SaloonInputFiles --> SaloonServices
        end
        
        Bakery --> BakeryFiles
        Saloon --> SaloonFiles
    end
    
    subgraph Database [Supabase Database]
        direction TB
        TenantConfigs[(tenant_configs)]
        CallDetails[(call_details)]
        Notifications[(notifications)]
        
        TenantConfigs -->|1:N| CallDetails
        CallDetails -->|1:N| Notifications
    end
    
    subgraph ServerComponents [Server Components]
        direction TB
        WebSocketServer[WebSocket Server]
        TranscriptAnalyzer[Transcript Analyzer]
        ActionService[Action Service]
        WhatsAppService[WhatsApp Service]
        
        WebSocketServer --> TranscriptAnalyzer
        TranscriptAnalyzer --> ActionService
        ActionService --> WhatsAppService
    end
    
    TenantRepository -->|Load prompts| ServerComponents
    Database -->|Configuration| ServerComponents
    ServerComponents -->|Store data| Database
    
    classDef files fill:#fcf,stroke:#333,stroke-width:1px;
    classDef components fill:#cff,stroke:#333,stroke-width:2px;
    classDef db fill:#ffc,stroke:#333,stroke-width:2px;
    
    class BakeryFiles,SaloonFiles files;
    class ServerComponents components;
    class Database db;
```

## Database Schema

```mermaid
erDiagram
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
        text session_id
        text call_sid
        text tenant FK
        jsonb transcript
        text call_type
        jsonb critical_call_details
        timestamptz created_at
    }
    
    EXOTEL_CALL_DETAILS {
        bigint id PK
        text call_sid UK
        text tenant
        jsonb exotel_data
        timestamptz created_at
    }
    
    NOTIFICATIONS {
        bigint id PK
        text call_sid FK
        text recipient
        text recipient_type
        text status
        jsonb payload
        jsonb details
        timestamptz created_at
    }
    
    TENANT_CONFIGS ||--o{ CALL_DETAILS : "has"
    CALL_DETAILS ||--o{ NOTIFICATIONS : "triggers"
    EXOTEL_CALL_DETAILS ||--o{ NOTIFICATIONS : "provides_contact_info"
```
