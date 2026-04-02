// Package whimtail embeds a Tailscale tsnet node into the Whim Android apps.
// It exposes a local SOCKS5 proxy so the recorder's OkHttpClient can reach
// any Tailscale peer without the system VPN service.
package whimtail

import (
	"context"
	"fmt"
	"log"
	"net"
	"os"
	"sync"

	"tailscale.com/net/socks5"
	"tailscale.com/tsnet"
)

const socksPort = 1055

var (
	mu        sync.Mutex
	server    *tsnet.Server
	socksLn   net.Listener
	started   bool
)

// silentLogf discards all tsnet chatter so only our explicit logs appear.
func silentLogf(string, ...any) {}

// Start brings up the embedded Tailscale node ("whim-droid") and a SOCKS5
// proxy on 127.0.0.1:1055. OkHttpClient should be configured to use this
// proxy address.
//
// dataDir:    writable directory for Tailscale state
// authKey:    TS_AUTHKEY (can be empty for interactive auth)
// controlURL: Headscale/Tailscale control URL (empty = default login server)
func Start(dataDir, authKey, controlURL string) (string, error) {
	mu.Lock()
	defer mu.Unlock()

	if started {
		return fmt.Sprintf("127.0.0.1:%d", socksPort), nil
	}

	if dataDir != "" {
		os.MkdirAll(dataDir, 0700)
	}

	server = &tsnet.Server{
		Hostname: "whim-droid",
		Dir:      dataDir,
		Logf:     silentLogf,
	}

	if authKey != "" {
		server.AuthKey = authKey
	}
	if controlURL != "" {
		server.ControlURL = controlURL
	}

	if err := server.Start(); err != nil {
		return "", fmt.Errorf("tsnet start failed: %w", err)
	}

	ln, err := net.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", socksPort))
	if err != nil {
		server.Close()
		return "", fmt.Errorf("socks listener failed: %w", err)
	}
	socksLn = ln

	srv := &socks5.Server{
		Dialer: func(ctx context.Context, network, addr string) (net.Conn, error) {
			return server.Dial(ctx, network, addr)
		},
		Logf: silentLogf,
	}
	go srv.Serve(ln)

	started = true
	log.Println("Node Ready")
	return fmt.Sprintf("127.0.0.1:%d", socksPort), nil
}

// Stop shuts down the SOCKS5 proxy and Tailscale node.
func Stop() {
	mu.Lock()
	defer mu.Unlock()

	if !started {
		return
	}

	if socksLn != nil {
		socksLn.Close()
	}
	if server != nil {
		server.Close()
	}

	started = false
	log.Println("Node Ready: stopped")
}

// IsRunning returns whether the embedded Tailscale node is active.
func IsRunning() bool {
	mu.Lock()
	defer mu.Unlock()
	return started
}

// GetProxyAddr returns "127.0.0.1:1055" if running, empty string otherwise.
func GetProxyAddr() string {
	mu.Lock()
	defer mu.Unlock()
	if !started {
		return ""
	}
	return fmt.Sprintf("127.0.0.1:%d", socksPort)
}
