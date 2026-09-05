package gr.geekon.labels;

import android.Manifest;
import android.annotation.SuppressLint;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothSocket;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.util.Base64;
import android.webkit.JavascriptInterface;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.app.Activity;

import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.util.Set;
import java.util.UUID;

/**
 * GeekOn Labels — εκτύπωση ετικετών απευθείας από tablet/κινητό Android
 * σε θερμικούς εκτυπωτές μέσω Bluetooth (SPP) ή WiFi (θύρα 9100).
 *
 * Το γραφικό περιβάλλον είναι η σελίδα assets/app.html· η επικοινωνία με τον
 * εκτυπωτή γίνεται από εδώ, μέσω της γέφυρας «Android» που εκτίθεται στη JS.
 */
public class MainActivity extends Activity {

    private static final UUID SPP =
            UUID.fromString("00001101-0000-1000-8000-00805F9B34FB");

    private WebView web;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle saved) {
        super.onCreate(saved);
        askPermissions();

        web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(true);
        s.setUseWideViewPort(true);
        s.setLoadWithOverviewMode(false);
        s.setTextZoom(100);
        web.setWebViewClient(new WebViewClient());
        web.addJavascriptInterface(new Bridge(), "Android");
        web.loadUrl("file:///android_asset/app.html");
        setContentView(web);
    }

    private void askPermissions() {
        try {
            if (Build.VERSION.SDK_INT >= 31) {
                if (checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT)
                        != PackageManager.PERMISSION_GRANTED) {
                    requestPermissions(new String[]{
                            Manifest.permission.BLUETOOTH_CONNECT,
                            Manifest.permission.BLUETOOTH_SCAN}, 1);
                }
            }
        } catch (Throwable ignored) {
        }
    }

    @Override
    public void onBackPressed() {
        if (web != null && web.canGoBack()) web.goBack();
        else super.onBackPressed();
    }

    /** Γέφυρα προς τη JavaScript της σελίδας. */
    public class Bridge {

        /** Λίστα ζευγαρωμένων συσκευών Bluetooth ως JSON. */
        @JavascriptInterface
        @SuppressLint("MissingPermission")
        public String devices() {
            StringBuilder sb = new StringBuilder("[");
            try {
                BluetoothAdapter ad = BluetoothAdapter.getDefaultAdapter();
                if (ad == null) return "[]";
                Set<BluetoothDevice> set = ad.getBondedDevices();
                boolean first = true;
                for (BluetoothDevice d : set) {
                    String name = d.getName() == null ? d.getAddress() : d.getName();
                    if (!first) sb.append(',');
                    first = false;
                    sb.append("{\"name\":\"").append(esc(name))
                      .append("\",\"address\":\"").append(esc(d.getAddress())).append("\"}");
                }
            } catch (Throwable t) {
                return "[]";
            }
            return sb.append(']').toString();
        }

        /** Εκτύπωση μέσω Bluetooth. Επιστρέφει "OK" ή "ERR: …". */
        @JavascriptInterface
        @SuppressLint("MissingPermission")
        public String printBt(String address, String base64) {
            BluetoothSocket sock = null;
            try {
                byte[] data = Base64.decode(base64, Base64.DEFAULT);
                BluetoothAdapter ad = BluetoothAdapter.getDefaultAdapter();
                if (ad == null) return "ERR: no bluetooth";
                if (!ad.isEnabled()) return "ERR: bluetooth off";
                BluetoothDevice dev = ad.getRemoteDevice(address);
                try {
                    sock = dev.createRfcommSocketToServiceRecord(SPP);
                    sock.connect();
                } catch (Exception first) {
                    // εφεδρικός τρόπος σύνδεσης για «δύστροπους» εκτυπωτές
                    try {
                        if (sock != null) sock.close();
                    } catch (Exception ignored) {
                    }
                    sock = (BluetoothSocket) dev.getClass()
                            .getMethod("createRfcommSocket", int.class)
                            .invoke(dev, 1);
                    if (sock == null) throw first;
                    sock.connect();
                }
                OutputStream out = sock.getOutputStream();
                // αποστολή σε κομμάτια — μεγάλες εικόνες «πνίγουν» το SPP
                int chunk = 512;
                for (int i = 0; i < data.length; i += chunk) {
                    int n = Math.min(chunk, data.length - i);
                    out.write(data, i, n);
                    out.flush();
                    Thread.sleep(12);
                }
                Thread.sleep(400);   // να προλάβει να τυπώσει πριν κλείσουμε
                out.close();
                return "OK";
            } catch (Throwable t) {
                return "ERR: " + t.getMessage();
            } finally {
                try {
                    if (sock != null) sock.close();
                } catch (Exception ignored) {
                }
            }
        }

        /** Εκτύπωση σε δικτυακό εκτυπωτή (WiFi/Ethernet). */
        @JavascriptInterface
        public String printTcp(String host, int port, String base64) {
            Socket sock = null;
            try {
                byte[] data = Base64.decode(base64, Base64.DEFAULT);
                sock = new Socket();
                sock.connect(new InetSocketAddress(host, port <= 0 ? 9100 : port), 8000);
                OutputStream out = sock.getOutputStream();
                out.write(data);
                out.flush();
                Thread.sleep(300);
                out.close();
                return "OK";
            } catch (Throwable t) {
                return "ERR: " + t.getMessage();
            } finally {
                try {
                    if (sock != null) sock.close();
                } catch (Exception ignored) {
                }
            }
        }

        /** Ζητά τα δικαιώματα Bluetooth (Android 12+). */
        @JavascriptInterface
        public void requestPerms() {
            runOnUiThread(MainActivity.this::askPermissions);
        }

        private String esc(String s) {
            return s == null ? "" : s.replace("\\", "\\\\").replace("\"", "\\\"");
        }
    }
}
