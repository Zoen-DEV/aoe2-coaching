// ---------------------------------------------------------------------------
// Motor de la guia: estado de cada jugador, avance de pasos y panel.
// Usa las funciones generadas desde la build order (guiaTomarDatos,
// guiaCumplido, guiaProgreso, guiaTitulo, guiaTexto, guiaIcono, guiaReferencia...).
//
// Pantalla (un solo panel de instrucciones, arriba en el centro):
//   Fast Castle 27+2 . Paso 5 de 16 . vas 0:12 tarde
//   [x] 3. Campamento y 4 lenadores . 3:12
//   [x] 4. Primer jabali . 3:41 (+31 s)
//   >> 5. Con el aldeano 12, construye una casa y un molino... (ref. 5:40)
//        Casas 2/3 . Molino 0/1 . Bayas 1/5
//   [ ] 6. Segundo jabali, 14 en comida . 6:25
//   ...
// Debajo, un aviso rojo cuando falta espacio de poblacion.
// El panel solo admite un color, al principio del texto: las etiquetas de
// color a mitad de texto salen escritas tal cual.
// ---------------------------------------------------------------------------

const int cGuiaMaxJugadores = 9;

// IDs de los arrays de estado. Se crean en guiaIniciar.
int gGuiaPaso = -1;        // paso actual de cada jugador; cGuiaNumPasos = guia terminada
int gGuiaHecho = -1;       // segundo en que se cumplio cada paso: -1 = aun no, -2 = saltado; indice jugador * cGuiaNumPasos + paso
int gGuiaPanel = -1;       // ultimo texto del panel, para no redibujarlo si no cambia
int gGuiaAvisoCasas = -1;  // segundo del ultimo aviso de casas

void guiaIniciar()
{
    if (gGuiaPaso >= 0)
    {
        return;
    }
    gGuiaPaso = xsArrayCreateInt(cGuiaMaxJugadores, 0, "guiaPaso");
    gGuiaHecho = xsArrayCreateInt(cGuiaMaxJugadores * cGuiaNumPasos, -1, "guiaHecho");
    gGuiaPanel = xsArrayCreateString(cGuiaMaxJugadores, "", "guiaPanel");
    gGuiaAvisoCasas = xsArrayCreateInt(cGuiaMaxJugadores, 0, "guiaAvisoCasas");
    gGuiaDatos = xsArrayCreateInt(cGuiaNumDatos, 0, "guiaDatos");
}

int guiaIndice(int jugador = 0, int paso = 0)
{
    int indice = jugador * cGuiaNumPasos + paso;
    return (indice);
}

int guiaHoraHecho(int jugador = 0, int paso = 0)
{
    int t = xsArrayGetInt(gGuiaHecho, guiaIndice(jugador, paso));
    return (t);
}

// Desfase corto para las lineas hechas: nada si esta dentro del margen.
string guiaDesfase(int jugador = 0, int paso = 0)
{
    string s = "";
    int diferencia = guiaHoraHecho(jugador, paso) - guiaReferencia(jugador, paso);
    if (diferencia > cGuiaMargen)
    {
        s = " (+" + guiaDuracion(diferencia) + ")";
    }
    else if (diferencia < 0 - cGuiaMargen)
    {
        s = " (-" + guiaDuracion(0 - diferencia) + ")";
    }
    return (s);
}

// Ritmo para la cabecera, segun el ultimo paso hecho.
string guiaRitmo(int jugador = 0, int paso = 0)
{
    string s = "a tiempo";
    int diferencia = guiaHoraHecho(jugador, paso) - guiaReferencia(jugador, paso);
    if (diferencia > cGuiaMargen)
    {
        s = "vas " + guiaDuracion(diferencia) + " tarde";
    }
    else if (diferencia < 0 - cGuiaMargen)
    {
        s = "vas " + guiaDuracion(0 - diferencia) + " adelantado";
    }
    return (s);
}

string guiaLineaHecho(int jugador = 0, int paso = 0)
{
    string s = "";
    int t = guiaHoraHecho(jugador, paso);
    if (t < 0)
    {
        s = "[-] " + (paso + 1) + ". " + guiaTitulo(jugador, paso) + " · sin hacer";
    }
    else
    {
        s = "[x] " + (paso + 1) + ". " + guiaTitulo(jugador, paso) + " · " + guiaReloj(t) + guiaDesfase(jugador, paso);
    }
    return (s);
}

string guiaLineaActual(int jugador = 0, int paso = 0)
{
    string s = "» " + (paso + 1) + ". " + guiaTexto(jugador, paso) + " (ref. " + guiaReloj(guiaReferencia(jugador, paso)) + ")";
    s = s + "\n     " + guiaProgreso(jugador, paso);
    return (s);
}

string guiaLineaSiguiente(int jugador = 0, int paso = 0)
{
    string s = "[ ] " + (paso + 1) + ". " + guiaTitulo(jugador, paso) + " · " + guiaReloj(guiaReferencia(jugador, paso));
    return (s);
}

// Panel completo: cabecera, ultimos pasos hechos, paso actual y siguientes.
string guiaPanel(int jugador = 0, int paso = 0)
{
    string s = guiaNombre() + " · Paso " + (paso + 1) + " de " + cGuiaNumPasos;
    if (paso > 0)
    {
        s = s + " · " + guiaRitmo(jugador, paso - 1);
    }
    int i = paso - cGuiaHechosVisibles;
    if (i < 0)
    {
        i = 0;
    }
    while (i < paso)
    {
        s = s + "\n" + guiaLineaHecho(jugador, i);
        i++;
    }
    s = s + "\n" + guiaLineaActual(jugador, paso);
    i = paso + 1;
    int hasta = paso + cGuiaSiguientesVisibles;
    while (i <= hasta)
    {
        if (i < cGuiaNumPasos)
        {
            s = s + "\n" + guiaLineaSiguiente(jugador, i);
        }
        i++;
    }
    return (s);
}

// Panel de despedida: ultimos pasos, hora de llegada y siguiente objetivo.
string guiaPanelFinal(int jugador = 0)
{
    int ultimo = cGuiaNumPasos - 1;
    string s = guiaNombre() + " · ¡Guía completada!";
    int i = cGuiaNumPasos - cGuiaHechosVisibles - 1;
    if (i < 0)
    {
        i = 0;
    }
    while (i < cGuiaNumPasos)
    {
        s = s + "\n" + guiaLineaHecho(jugador, i);
        i++;
    }
    if (guiaHoraHecho(jugador, ultimo) >= 0)
    {
        s = s + "\n" + guiaTitulo(jugador, ultimo) + " a las " + guiaReloj(guiaHoraHecho(jugador, ultimo)) + " (ref. " + guiaReloj(guiaReferencia(jugador, ultimo)) + ", " + guiaRitmo(jugador, ultimo) + ").";
    }
    s = s + "\n" + guiaMensajeFinal();
    return (s);
}

// Aviso si queda poco espacio de poblacion y no hay ninguna casa en obra.
// cAttributePopulationCap es el espacio LIBRE (vivienda - poblacion), no el limite.
void guiaAvisarCasas(int jugador = 0, int t = 0)
{
    if (cGuiaAvisoCasas == 0)
    {
        return;
    }
    if (t < 20)
    {
        return;
    }
    int libre = xsPlayerAttribute(jugador, cAttributePopulationCap);
    if (libre > 2)
    {
        return;
    }
    int enObra = guiaUnidades(jugador, cGuiaIdCasa) - guiaTerminados(jugador, cGuiaIdCasa);
    if (enObra > 0)
    {
        return;
    }
    if (t - xsArrayGetInt(gGuiaAvisoCasas, jugador) < 20)
    {
        return;
    }
    xsArraySetInt(gGuiaAvisoCasas, jugador, t);
    int poblacion = xsPlayerAttribute(jugador, cAttributePopulation);
    int capacidad = poblacion + libre;
    string s = "<RED>Población " + poblacion + "/" + capacidad + ": construye una casa o el centro urbano se parará.";
    xsDisplayInstructions(s, 8, jugador, cGuiaIdCasa, cPanelBottom, false, true, "", jugador);
}

// Vuelca el estado del jugador local a un archivo .xsdat (con el nombre del mapa)
// para el overlay externo. Formato: enteros de 32 bits, ver overlay/lector.py.
// Escribir un archivo es local a cada equipo y no afecta a la partida.
void guiaEscribirEstado(int jugador = 0, int t = 0, int paso = 0)
{
    if (cGuiaOverlay == 0)
    {
        return;
    }
    if (xsUnsyncGetLocalPlayerId() != jugador)
    {
        return;
    }
    bool abierto = xsCreateFile(false);
    if (abierto == false)
    {
        return;
    }
    int poblacion = xsPlayerAttribute(jugador, cAttributePopulation);
    int libre = xsPlayerAttribute(jugador, cAttributePopulationCap);
    int enObra = guiaUnidades(jugador, cGuiaIdCasa) - guiaTerminados(jugador, cGuiaIdCasa);
    int edad = guiaEdad(jugador);
    xsWriteInt(4722);
    xsWriteInt(3);
    xsWriteInt(cGuiaCodigo);
    xsWriteInt(t);
    xsWriteInt(jugador);
    xsWriteInt(paso);
    xsWriteInt(cGuiaNumPasos);
    for (k = 0; < cGuiaNumPasos)
    {
        int hora = guiaHoraHecho(jugador, k);
        xsWriteInt(hora);
    }
    xsWriteInt(cGuiaNumDatos);
    for (k = 0; < cGuiaNumDatos)
    {
        int dato = guiaDato(k);
        xsWriteInt(dato);
    }
    guiaEscribirTechs(jugador);
    xsWriteInt(edad);
    xsWriteInt(poblacion);
    xsWriteInt(libre);
    xsWriteInt(enObra);
    guiaEscribirTierlist(jugador);
    xsWriteInt(9999);
    xsCloseFile();
}

void guiaActualizarJugador(int jugador = 0, int t = 0)
{
    int paso = 0;
    int i = 0;
    int indice = 0;
    int nuevos = 0;
    bool sonar = false;
    bool meta = false;

    if (xsGetPlayerType(jugador) != cPlayerTypeHuman)
    {
        return;
    }
    if (xsGetPlayerInGame(jugador) == false)
    {
        return;
    }
    paso = xsArrayGetInt(gGuiaPaso, jugador);
    guiaTomarDatos(jugador);
    if (paso >= cGuiaNumPasos)
    {
        guiaEscribirEstado(jugador, t, paso);
        return;
    }

    // 1. Anotar la hora de los pasos que se cumplen ahora. Se miran tambien los
    //    pasos siguientes, para no atascarse si el jugador cambia el orden.
    i = paso;
    while (i < cGuiaNumPasos)
    {
        indice = guiaIndice(jugador, i);
        if (xsArrayGetInt(gGuiaHecho, indice) == -1)
        {
            if (guiaCumplido(jugador, i) == true)
            {
                xsArraySetInt(gGuiaHecho, indice, t);
            }
        }
        i++;
    }

    // 2. Avanzar, en orden, por los pasos ya cumplidos. Si ya se cumplio el
    //    ultimo paso (la meta), la guia se cierra y los que falten quedan como saltados.
    if (guiaHoraHecho(jugador, cGuiaNumPasos - 1) >= 0)
    {
        meta = true;
    }
    while (paso < cGuiaNumPasos)
    {
        indice = guiaIndice(jugador, paso);
        if (xsArrayGetInt(gGuiaHecho, indice) < 0)
        {
            if (meta == false)
            {
                break;
            }
            xsArraySetInt(gGuiaHecho, indice, -2);
        }
        paso++;
        nuevos++;
    }
    xsArraySetInt(gGuiaPaso, jugador, paso);
    if (nuevos > 0)
    {
        sonar = true;
    }

    // 3. Estado para el overlay externo.
    guiaEscribirEstado(jugador, t, paso);
    if (cGuiaPanelJuego == 0)
    {
        return;
    }

    // 4. Panel del juego (opcional), solo si cambio (con sonido si hay paso nuevo o es el primero).
    if (paso >= cGuiaNumPasos)
    {
        xsDisplayInstructions(guiaPanelFinal(jugador), 90, jugador, guiaIcono(cGuiaNumPasos - 1), cPanelTop, false, true, "", jugador);
        return;
    }
    string panel = guiaPanel(jugador, paso);
    if (panel != xsArrayGetString(gGuiaPanel, jugador))
    {
        if (xsArrayGetString(gGuiaPanel, jugador) == "")
        {
            sonar = true;
        }
        xsArraySetString(gGuiaPanel, jugador, panel);
        xsDisplayInstructions(panel, 3600, jugador, guiaIcono(paso), cPanelTop, false, sonar, "", jugador);
    }
    guiaAvisarCasas(jugador, t);
}

rule guiaActualizar
    active
    minInterval 1
    maxInterval 1
{
    guiaIniciar();
    int t = xsGetGameTime();
    for (jugador = 1; <= xsGetNumPlayers())
    {
        guiaActualizarJugador(jugador, t);
    }
}

void main()
{
    guiaIniciar();
}
