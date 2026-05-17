// SPDX-License-Identifier: MIT
//
// OpenWSFZ daemon entry point.
//
// Owns: CLI parsing, structured startup/shutdown logging, signal-driven
// graceful shutdown, the HTTP server (Drogon), the static asset root,
// and registration of the WebSocket controller. All decoder, audio,
// and rig-control capabilities slot in via later changes; nothing
// protocol-related lives here.
//
// Wire contract for /ws is specified in
//   openspec/changes/add-project-skeleton/specs/web-control-api/spec.md
// HTTP and lifecycle requirements in
//   openspec/changes/add-project-skeleton/specs/daemon-core/spec.md
// Architecture overview in
//   docs/ARCHITECTURE.md

#include <atomic>
#include <chrono>
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <iomanip>
#include <iostream>
#include <optional>
#include <sstream>
#include <string>
#include <string_view>

#include <drogon/drogon.h>
#include <json/json.h>

#include "openwsfz/version.hpp"
#include "WsController.h"

namespace fs = std::filesystem;

namespace {

// ----- structured logging -------------------------------------------------

enum class LogLevel { INFO, WARN, ERROR_ };

const char* level_name(LogLevel l)
{
    switch (l) {
        case LogLevel::INFO:   return "INFO";
        case LogLevel::WARN:   return "WARN";
        case LogLevel::ERROR_: return "ERROR";
    }
    return "INFO";
}

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

// Single-line, greppable: <ts> <LEVEL> <component> <message>
void log_line(LogLevel level, std::string_view component, std::string_view msg)
{
    std::cerr << iso8601_now() << ' '
              << level_name(level) << ' '
              << component << ' '
              << msg << '\n';
    std::cerr.flush();
}

// ----- uptime -------------------------------------------------------------

const auto kProcessStart = std::chrono::steady_clock::now();

double uptime_seconds()
{
    const auto now = std::chrono::steady_clock::now();
    const std::chrono::duration<double> dt = now - kProcessStart;
    return dt.count();
}

// ----- CLI ----------------------------------------------------------------

struct Options {
    std::string bind     = "127.0.0.1";
    std::uint16_t port   = 8080;
    fs::path     docRoot;  // resolved at runtime; default = exe-dir/web
    bool         show_help = false;
};

void print_usage(std::ostream& out)
{
    out << "openwsfz " << OPENWSFZ_VERSION_STRING
        << " (git " << OPENWSFZ_GIT_SHA << ")\n"
        << "Usage: openwsfz [options]\n"
        << "\n"
        << "Options:\n"
        << "  --bind <host>      Bind address (default: 127.0.0.1)\n"
        << "  --port <port>      TCP port (default: 8080)\n"
        << "  --doc-root <dir>   Static asset directory (default: <exe-dir>/web)\n"
        << "  -h, --help         Show this help and exit\n";
}

// Returns std::nullopt on success; returns an error message on parse failure.
std::optional<std::string> parse_args(int argc, char** argv, Options& out)
{
    auto take_value = [&](int& i, const char* flag) -> std::optional<std::string> {
        if (i + 1 >= argc) {
            return std::string("flag '") + flag + "' requires a value";
        }
        return std::string{argv[++i]};
    };

    for (int i = 1; i < argc; ++i) {
        const std::string a = argv[i];
        if (a == "-h" || a == "--help") {
            out.show_help = true;
            return std::nullopt;
        } else if (a == "--bind") {
            auto v = take_value(i, "--bind");
            if (!v) return v;
            out.bind = *v;
        } else if (a == "--port") {
            auto v = take_value(i, "--port");
            if (!v) return v;
            try {
                const int p = std::stoi(*v);
                if (p < 1 || p > 65535) {
                    return "port out of range: " + *v;
                }
                out.port = static_cast<std::uint16_t>(p);
            } catch (...) {
                return "port not an integer: " + *v;
            }
        } else if (a == "--doc-root") {
            auto v = take_value(i, "--doc-root");
            if (!v) return v;
            out.docRoot = *v;
        } else {
            return "unknown flag: " + a;
        }
    }
    return std::nullopt;
}

// ----- signal handling ----------------------------------------------------

std::atomic<bool> g_shutdown_requested{false};
const char*       g_shutdown_signal = "";

void on_signal(int sig)
{
    g_shutdown_requested.store(true);
    g_shutdown_signal = (sig == SIGINT) ? "SIGINT" : "SIGTERM";
    // Drogon's quit() is safe to call from a signal handler on the
    // platforms we target; it just sets a flag.
    drogon::app().quit();
}

// ----- exe dir ------------------------------------------------------------

fs::path executable_dir()
{
#if defined(_WIN32)
    wchar_t buf[32768];
    DWORD n = GetModuleFileNameW(nullptr, buf, sizeof(buf) / sizeof(wchar_t));
    if (n == 0) return fs::current_path();
    return fs::path(buf, buf + n).parent_path();
#else
    // /proc/self/exe on Linux; on macOS this works in many cases but the
    // canonical answer is _NSGetExecutablePath. For the skeleton, fall
    // back to argv[0]'s directory if /proc/self/exe is missing.
    std::error_code ec;
    fs::path p = fs::read_symlink("/proc/self/exe", ec);
    if (!ec) return p.parent_path();
    return fs::current_path();
#endif
}

}  // namespace

#if defined(_WIN32)
// We use GetModuleFileNameW above; pull in <windows.h> after the std
// headers so its macros don't clobber our own identifiers.
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#endif

int main(int argc, char** argv)
{
    Options opts;
    if (auto err = parse_args(argc, argv, opts); err) {
        std::cerr << "error: " << *err << "\n\n";
        print_usage(std::cerr);
        return 2;
    }
    if (opts.show_help) {
        print_usage(std::cout);
        return 0;
    }

    // Resolve doc root.
    if (opts.docRoot.empty()) {
        opts.docRoot = executable_dir() / "web";
        if (!fs::exists(opts.docRoot)) {
            // Fallback: running from source tree.
            const fs::path fromSrc = fs::current_path() / "web";
            if (fs::exists(fromSrc)) {
                opts.docRoot = fromSrc;
            }
        }
    }
    if (!fs::exists(opts.docRoot)) {
        log_line(LogLevel::ERROR_, "startup",
                 "doc-root not found: " + opts.docRoot.string());
        return 1;
    }

    // Configure Drogon.
    auto& app = drogon::app();
    app.setLogLevel(trantor::Logger::kInfo);
    app.setDocumentRoot(opts.docRoot.string());
    app.addListener(opts.bind, opts.port);

    // Health endpoint: /api/health -> {status, version, uptime_seconds}.
    app.registerHandler(
        "/api/health",
        [](const drogon::HttpRequestPtr&,
           std::function<void(const drogon::HttpResponsePtr&)>&& callback) {
            Json::Value body;
            body["status"]         = "ok";
            body["version"]        = OPENWSFZ_VERSION_STRING;
            body["git_sha"]        = OPENWSFZ_GIT_SHA;
            body["uptime_seconds"] = uptime_seconds();
            auto resp = drogon::HttpResponse::newHttpJsonResponse(body);
            resp->setStatusCode(drogon::k200OK);
            callback(resp);
        },
        {drogon::Get});

    // WebSocket controller for /ws (AutoCreation=false, register manually).
    auto ws = std::make_shared<openwsfz::WsController>();
    drogon::app().registerController(ws);

    // Signal handlers.
    std::signal(SIGINT,  on_signal);
    std::signal(SIGTERM, on_signal);

    {
        std::ostringstream msg;
        msg << "openwsfz " << OPENWSFZ_VERSION_STRING
            << " (git " << OPENWSFZ_GIT_SHA << ")"
            << " listening on http://" << opts.bind << ":" << opts.port
            << " doc-root=" << opts.docRoot.string();
        log_line(LogLevel::INFO, "startup", msg.str());
    }

    app.run();

    {
        std::ostringstream msg;
        msg << "exiting after " << std::fixed << std::setprecision(3)
            << uptime_seconds() << "s reason="
            << (g_shutdown_signal[0] ? g_shutdown_signal : "app.run-returned");
        log_line(LogLevel::INFO, "shutdown", msg.str());
    }
    return 0;
}
