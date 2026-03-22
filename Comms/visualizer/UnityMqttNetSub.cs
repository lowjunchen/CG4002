using System;
using System.IO;
using System.Security.Cryptography.X509Certificates;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;
using MQTTnet;
using MQTTnet.Client;

public class UnityMqttNetSub : MonoBehaviour
{
    [Header("Broker")]
    public string host = "Yeos-MacBook-Pro.local";
    public int port = 8883;

    [Header("Topics")]
    public string topic1 = "sensors/device/1";
    public string topic2 = "sensors/device/2";

    [Header("TLS")]
    public string caFile = "ca.crt";         // in StreamingAssets
    public string pfxFile = "unity_pub.pfx";  // in StreamingAssets
    public string pfxPassword = "capstone";

    private IMqttClient client;

    async void Start()
    {
        var caPath = Path.Combine(Application.streamingAssetsPath, caFile);
        var pfxPath = Path.Combine(Application.streamingAssetsPath, pfxFile);

        Debug.Log($"CA path: {caPath} exists={File.Exists(caPath)}");
        Debug.Log($"PFX path: {pfxPath} exists={File.Exists(pfxPath)}");

        var caCert = new X509Certificate2(caPath);
        var clientCert = new X509Certificate2(pfxPath, pfxPassword);

        var tlsOptions = new MqttClientTlsOptionsBuilder()
            .UseTls()
            .WithClientCertificates(new[] { clientCert })
            .WithCertificateValidationHandler(context =>
            {
                var serverCert = new X509Certificate2(context.Certificate);
                var chain = new X509Chain();
                chain.ChainPolicy.ExtraStore.Add(caCert);
                chain.ChainPolicy.VerificationFlags = X509VerificationFlags.AllowUnknownCertificateAuthority;
                chain.ChainPolicy.RevocationMode = X509RevocationMode.NoCheck;
                var ok = chain.Build(serverCert);
                if (!ok)
                {
                    foreach (var s in chain.ChainStatus)
                        Debug.LogError($"TLS chain error: {s.StatusInformation}");
                }
                return ok;
            })
            .Build();

        var factory = new MqttFactory();
        client = factory.CreateMqttClient();

        client.ApplicationMessageReceivedAsync += e =>
        {
            var payload = e.ApplicationMessage.PayloadSegment.ToArray();
            var msg = Encoding.UTF8.GetString(payload);
            Debug.Log($"[{e.ApplicationMessage.Topic}] {msg}");
            return Task.CompletedTask;
        };

        client.ConnectedAsync += e =>
        {
            Debug.Log("MQTT CONNECT OK");
            return Task.CompletedTask;
        };

        client.DisconnectedAsync += e =>
        {
            Debug.LogError("MQTT DISCONNECTED");
            return Task.CompletedTask;
        };

        var options = new MqttClientOptionsBuilder()
            .WithClientId("unity_sub_" + Guid.NewGuid().ToString("N"))
            .WithTcpServer(host, port)
            .WithCleanSession()
            .WithTlsOptions(tlsOptions)
            .Build();

        try
        {
            await client.ConnectAsync(options, CancellationToken.None);
            await client.SubscribeAsync(topic1);
            await client.SubscribeAsync(topic2);
            Debug.Log($"Subscribed: {topic1}, {topic2}");
        }
        catch (Exception ex)
        {
            Debug.LogError("MQTT CONNECT FAIL: " + ex);
        }
    }

    async void OnApplicationQuit()
    {
        if (client != null && client.IsConnected)
            await client.DisconnectAsync();
    }
}
