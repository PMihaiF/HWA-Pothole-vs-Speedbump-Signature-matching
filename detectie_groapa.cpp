#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <cmath>

using namespace std;

// Parametrii sistemului optimizați pentru hardware
#define WINDOW_SIZE 16          // Putere a lui 2 pentru a elimina divizarea grea pe FPGA
#define PRAG_ACCELERATIE 3.0 // Pragul în m/s^2 (sensibil la variații de ~0.25 G)

// ---------------------------------------------------------
// FUNCȚIA CORE PENTRU FPGA (Top-Level Function pentru Vitis)
// ---------------------------------------------------------
int detectie_groapa(float acc_z) {
    // Directivă HLS pentru a procesa un eșantion per ciclu de ceas
    #pragma HLS PIPELINE II=1
    
    static float fereastra[WINDOW_SIZE] = {0};
    static float suma = 0.0f;
    static int index = 0;
    static bool buffer_plin = false;

    // 1. Optimizare O(1): Scădem valoarea veche care iese din fereastră
    float valoare_veche = fereastra[index];
    suma -= valoare_veche;

    // 2. Adăugăm valoarea nouă în vector și în sumă
    fereastra[index] = acc_z;
    suma += acc_z;

    // 3. Incrementare circulară a indexului
    index++;
    if (index >= WINDOW_SIZE) {
        index = 0;
        buffer_plin = true;
    }

    // Blocăm detecțiile până când fereastra se umple complet prima dată
    if (!buffer_plin) return 0;

    // 4. Calculăm media mobilă și diferența locală
    float media = suma / WINDOW_SIZE; 
    float diff = acc_z - media;

    // 5. Decizie de clasificare bazată pe semnul deviației
    if (std::abs(diff) > PRAG_ACCELERATIE) {
        return diff > 0 ? 1 : -1;
    }

    return 0;
}

// ---------------------------------------------------------
// TESTBENCH / MEDIUL DE SIMULARE SOFTWARE
// ---------------------------------------------------------
int main() {
    // Am actualizat numele fișierului pentru a citi exportul de la phyphox
    ifstream file("Raw Data.csv");
    string line;

    if (!file.is_open()) {
        cerr << "Eroare: Nu am putut deschide Raw Data.csv! Asigura-te ca fisierul este in acelasi director cu executabilul." << endl;
        return 1;
    }

    cout << "--- Incepere Simulare C++ (HLS Compatible) pe date Phyphox ---" << endl;
    int numar_esantion = 0;
    int detectii_totale = 0;
    bool first_line = true;

    while (getline(file, line)) {
        if (line.empty()) continue;
        stringstream ss(line);
        string item;
        float timp, ax, ay, az, abs_acc;

        // Filtrare header text din CSV-ul Phyphox
        if (first_line) {
            first_line = false;
            // Phyphox folosește "Time (s)" în header
            if (line.find("Time") != string::npos || line.find("timp") != string::npos) {
                continue;
            }
        }

        // Parsare linie cu linie (acum avem 5 coloane)
        try {
            getline(ss, item, ','); timp = stof(item);
            getline(ss, item, ','); ax = stof(item);
            getline(ss, item, ','); ay = stof(item);
            getline(ss, item, ','); az = stof(item);
            // Citim și a 5-a coloană (Absolute acceleration) pentru a finaliza linia corect
            getline(ss, item, ','); abs_acc = stof(item);
        } catch (...) {
            continue; // Ignoră eventualele linii corupte sau incomplete
        }

        numar_esantion++;
        
        // --- DOWNSAMPLING PENTRU A REGLA FRECVENȚA ---
        // Sărim peste 19 din 20 de eșantioane pentru a aduce datele de la 400Hz la 20Hz
        if (numar_esantion % 20 != 0) continue; 
        
        // Apelul funcției algoritmului principal
        int rezultat = detectie_groapa(az);
        
        if (rezultat != 0) {
            detectii_totale++;
            string tip = (rezultat > 0) ? "speedbump" : "pothole";
            cout << "[!] ALERTA: " << tip << " detectat la esantionul "
                 << numar_esantion << " (Timp: " << timp << "s | Acc Z: " << az << " m/s^2)" << endl;
        }
    }

    file.close();
    cout << "--- Simulare Incheiata ---" << endl;
    cout << "Total esantioane procesate: " << numar_esantion << endl;
    cout << "Total anomalii detectate:   " << detectii_totale << endl;
    
    return 0;
}