// SPDX-License-Identifier: MIT
//
// WebSocket controller for /ws.
//
// The wire contract is fully specified in
// openspec/changes/add-project-skeleton/specs/web-control-api/spec.md.
// In the skeleton we accept the JSON envelope {type, id, ts, payload?}
// and reply with:
//
//   * type:"pong"  for incoming type:"ping"
//   * type:"echo"  for any other recognised envelope
//   * type:"error" for malformed JSON or missing required fields
//
// Later capabilities extend the registry by inspecting `type` themselves.
#pragma once

#include <drogon/WebSocketController.h>

namespace openwsfz {

class WsController
    : public drogon::WebSocketController<WsController, /*AutoCreation=*/false>
{
public:
    void handleNewMessage(const drogon::WebSocketConnectionPtr& conn,
                          std::string&& message,
                          const drogon::WebSocketMessageType& type) override;

    void handleNewConnection(const drogon::HttpRequestPtr& req,
                             const drogon::WebSocketConnectionPtr& conn) override;

    void handleConnectionClosed(const drogon::WebSocketConnectionPtr& conn) override;

    // Drogon's macro-based path registration.
    WS_PATH_LIST_BEGIN
        WS_PATH_ADD("/ws");
    WS_PATH_LIST_END
};

}  // namespace openwsfz
