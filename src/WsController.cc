// SPDX-License-Identifier: MIT
#include "WsController.h"

#include <chrono>
#include <iomanip>
#include <sstream>
#include <string>

#include <json/json.h>
#include <trantor/utils/Logger.h>

namespace openwsfz {

namespace {

// ISO-8601 UTC millisecond timestamp, e.g. "2026-05-17T10:00:00.000Z".
std::string iso8601_now()
{
    using namespace std::chrono;
    const auto now = system_clock::now();
    const auto ms  = duration_cast<milliseconds>(now.time_since_epoch()) % 1000;
    const auto t   = system_clock::to_time_t(now);

    std::tm tm_utc{};
#if defined(_WIN32)
    gmtime_s(&tm_utc, &t);
#else
    gmtime_r(&t, &tm_utc);
#endif

    std::ostringstream os;
    os << std::put_time(&tm_utc, "%Y-%m-%dT%H:%M:%S")
       << '.' << std::setw(3) << std::setfill('0') << ms.count()
       << 'Z';
    return os.str();
}

void send_json(const drogon::WebSocketConnectionPtr& conn,
               const Json::Value& v)
{
    Json::StreamWriterBuilder b;
    b["indentation"] = "";
    conn->send(Json::writeString(b, v));
}

void send_error(const drogon::WebSocketConnectionPtr& conn,
                const Json::Value& maybeId,
                const std::string& message)
{
    Json::Value out;
    out["type"] = "error";
    out["id"]   = maybeId.isNull() ? Json::Value("") : maybeId;
    out["ts"]   = iso8601_now();
    out["payload"] = Json::Value(Json::objectValue);
    out["payload"]["message"] = message;
    send_json(conn, out);
}

}  // namespace

void WsController::handleNewConnection(const drogon::HttpRequestPtr& /*req*/,
                                       const drogon::WebSocketConnectionPtr& conn)
{
    LOG_INFO << "ws: client connected from "
             << conn->peerAddr().toIpPort();
}

void WsController::handleConnectionClosed(const drogon::WebSocketConnectionPtr& conn)
{
    LOG_INFO << "ws: client disconnected from "
             << conn->peerAddr().toIpPort();
}

void WsController::handleNewMessage(const drogon::WebSocketConnectionPtr& conn,
                                    std::string&& message,
                                    const drogon::WebSocketMessageType& type)
{
    // Only text frames carry the JSON envelope.
    if (type != drogon::WebSocketMessageType::Text) {
        send_error(conn, Json::Value(), "binary frames are not accepted");
        return;
    }

    Json::CharReaderBuilder rb;
    Json::Value envelope;
    std::string parse_errors;
    std::istringstream is(message);
    if (!Json::parseFromStream(rb, is, &envelope, &parse_errors)) {
        send_error(conn, Json::Value(), "malformed JSON: " + parse_errors);
        return;
    }
    if (!envelope.isObject()) {
        send_error(conn, Json::Value(), "envelope must be a JSON object");
        return;
    }

    const Json::Value& idField = envelope["id"];
    if (!envelope.isMember("type") || !envelope["type"].isString()) {
        send_error(conn, idField, "envelope is missing required string field 'type'");
        return;
    }
    if (!envelope.isMember("id") ||
        !(idField.isString() || idField.isIntegral())) {
        send_error(conn, Json::Value(),
                   "envelope is missing required field 'id' (string or integer)");
        return;
    }

    const std::string requested_type = envelope["type"].asString();

    if (requested_type == "ping") {
        Json::Value out;
        out["type"] = "pong";
        out["id"]   = idField;
        out["ts"]   = iso8601_now();
        Json::Value payload(Json::objectValue);
        payload["echoed"] = envelope.isMember("payload")
                                ? envelope["payload"]
                                : Json::Value(Json::objectValue);
        out["payload"] = payload;
        send_json(conn, out);
        return;
    }

    // Default: echo the original envelope wrapped under payload.original.
    Json::Value out;
    out["type"] = "echo";
    out["id"]   = idField;
    out["ts"]   = iso8601_now();
    Json::Value payload(Json::objectValue);
    payload["original"] = envelope;
    out["payload"] = payload;
    send_json(conn, out);
}

}  // namespace openwsfz
