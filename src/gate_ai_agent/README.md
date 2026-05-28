# Gate AI Agent

Webhook service for Azure OpenAI Realtime SIP calls.

## Runtime Settings

- `AZURE_OPENAI_ENDPOINT`: Azure OpenAI endpoint, for example `https://<resource>.openai.azure.com`
- `AZURE_OPENAI_API_KEY`: Azure OpenAI API key
- `AZURE_OPENAI_REALTIME_DEPLOYMENT`: realtime model deployment name
- `OPENAI_WEBHOOK_SECRET`: webhook signing secret returned when creating the Azure OpenAI webhook endpoint
- `GATE_AI_AGENT_NAME`: optional display name used in the first spoken response
- `GATE_AI_AGENT_VOICE`: optional realtime voice name

## Routes

- `GET /healthz`: health check
- `POST /webhook`: Azure OpenAI webhook endpoint for `realtime.call.incoming`

The webhook verifies the signature, accepts incoming SIP calls, opens a WebSocket to the realtime session, and sends the first greeting response.
